#!/usr/bin/env python3
"""
FreeRide - Free AI for OpenClaw
Automatically manage and switch between free AI models on OpenRouter
for unlimited free AI access.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from profiles import PROFILES, DEFAULT_PROFILE, VALID_PROFILES, get_profile


# Constants
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"
OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
CACHE_FILE = Path.home() / ".openclaw" / ".freeride-cache.json"
BENCHMARKS_FILE = Path(__file__).parent / "benchmarks.json"
CACHE_DURATION_HOURS = 6

# Tier scores for benchmark-based ranking
TIER_SCORES = {"S": 1.0, "A": 0.8, "B": 0.6, "C": 0.4, "unknown": 0.3}


def load_benchmarks() -> Dict[str, Any]:
    """Load benchmark data from benchmarks.json."""
    if not BENCHMARKS_FILE.exists():
        return {}
    try:
        return json.loads(BENCHMARKS_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def get_benchmark_tier(model_id: str, benchmarks: Dict = None) -> str:
    """Get the benchmark tier (S/A/B/C) for a model."""
    if benchmarks is None:
        benchmarks = load_benchmarks()
    
    tiers = benchmarks.get("tiers", {})
    model_lower = model_id.lower()
    
    for tier_name in ["S", "A", "B", "C"]:
        tier_data = tiers.get(tier_name, {})
        patterns = tier_data.get("patterns", [])
        for pattern in patterns:
            if pattern.lower() in model_lower:
                return tier_name
    
    return "unknown"


def get_benchmark_score(model_id: str, benchmarks: Dict = None) -> float:
    """Get a normalized benchmark score (0-1) for a model."""
    tier = get_benchmark_tier(model_id, benchmarks)
    return TIER_SCORES.get(tier, 0.3)


def matches_category_boost(model_id: str, category: str, benchmarks: Dict = None) -> bool:
    """Check if a model matches a category boost pattern."""
    if benchmarks is None:
        benchmarks = load_benchmarks()
    
    boosts = benchmarks.get("category_boosts", {})
    category_data = boosts.get(category, {})
    patterns = category_data.get("patterns", [])
    
    model_lower = model_id.lower()
    for pattern in patterns:
        if pattern.lower() in model_lower:
            return True
    return False


def is_router_model(model_id: str, benchmarks: Dict = None) -> bool:
    """Check if a model is a router/meta-model (not a real model)."""
    if benchmarks is None:
        benchmarks = load_benchmarks()
    
    routers = benchmarks.get("routers", {})
    patterns = routers.get("patterns", [])
    
    model_lower = model_id.lower()
    for pattern in patterns:
        if pattern.lower() in model_lower:
            return True
    return False


def parse_model_metadata(model: dict) -> Dict[str, Any]:
    """Extract metadata from model data for scoring."""
    model_id = model.get("id", "")
    name = model.get("name", "")
    architecture = model.get("architecture", {})
    
    # Parse model size from name (e.g., "70b", "235b", "8b")
    size_match = re.search(r"(\d+)b", model_id.lower() + name.lower())
    size_billions = int(size_match.group(1)) if size_match else 0
    
    # Normalize size score (0-1, with 70B+ being max)
    size_score = min(size_billions / 70, 1.0) if size_billions > 0 else 0.3
    
    # Get context length and normalize
    context_length = model.get("context_length", 0)
    context_score = min(context_length / 256_000, 1.0)
    
    # Check modalities
    input_modalities = architecture.get("input_modalities", [])
    is_vision_capable = "image" in input_modalities
    
    # Check for reasoning/thinking models
    is_reasoning_model = any(x in model_id.lower() for x in ["thinking", "r1", "reasoning"])
    
    # Check for coding models
    is_coding_model = any(x in model_id.lower() for x in ["coder", "code"])
    
    # Check tool support
    supported_params = model.get("supported_parameters", []) or []
    has_tools = "tools" in supported_params or "tool_choice" in supported_params
    
    # Capability score based on useful features
    capability_features = [
        has_tools,
        "response_format" in supported_params,
        "structured_outputs" in supported_params,
        is_reasoning_model,
        is_vision_capable
    ]
    capability_score = sum(capability_features) / len(capability_features)
    
    return {
        "model_id": model_id,
        "size_billions": size_billions,
        "size_score": size_score,
        "context_length": context_length,
        "context_score": context_score,
        "is_vision_capable": is_vision_capable,
        "is_reasoning_model": is_reasoning_model,
        "is_coding_model": is_coding_model,
        "has_tools": has_tools,
        "capability_score": capability_score,
        "input_modalities": input_modalities
    }


def get_api_key() -> Optional[str]:
    """Get OpenRouter API key from environment or OpenClaw config."""
    # Try environment first
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if api_key:
        return api_key

    # Try OpenClaw config
    if OPENCLAW_CONFIG_PATH.exists():
        try:
            config = json.loads(OPENCLAW_CONFIG_PATH.read_text())
            # Check env section
            api_key = config.get("env", {}).get("OPENROUTER_API_KEY")
            if api_key:
                return api_key
        except (json.JSONDecodeError, KeyError):
            pass

    return None


def fetch_all_models(api_key: str) -> list:
    """Fetch all models from OpenRouter API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(OPENROUTER_API_URL, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except requests.RequestException as e:
        print(f"Error fetching models: {e}")
        return []


def filter_free_models(models: list) -> list:
    """Filter models to only include free ones (pricing.prompt == 0)."""
    free_models = []

    for model in models:
        model_id = model.get("id", "")
        pricing = model.get("pricing", {})

        # Check if model is free (prompt cost is 0 or None)
        prompt_cost = pricing.get("prompt")
        if prompt_cost is not None:
            try:
                if float(prompt_cost) == 0:
                    free_models.append(model)
            except (ValueError, TypeError):
                pass

        # Also include models with :free suffix
        if ":free" in model_id and model not in free_models:
            free_models.append(model)

    return free_models


def calculate_model_score(model: dict, profile: str = "general", benchmarks: Dict = None) -> float:
    """Calculate a ranking score for a model based on profile-specific criteria."""
    if benchmarks is None:
        benchmarks = load_benchmarks()
    
    model_id = model.get("id", "")
    
    # Get profile configuration
    profile_config = get_profile(profile)
    weights = profile_config["weights"]
    
    # Parse model metadata
    metadata = parse_model_metadata(model)
    
    # Get benchmark score
    benchmark_score = get_benchmark_score(model_id, benchmarks)
    
    # Calculate weighted score
    score = (
        benchmark_score * weights["benchmark"] +
        metadata["size_score"] * weights["size"] +
        metadata["context_score"] * weights["context"] +
        metadata["capability_score"] * weights["capability"]
    )
    
    # Apply profile-specific boosts
    category_boost = profile_config.get("category_boost")
    if category_boost:
        boost_value = benchmarks.get("category_boosts", {}).get(category_boost, {}).get("boost", 1.0)
        
        if category_boost == "coding" and metadata["is_coding_model"]:
            score *= boost_value
        elif category_boost == "reasoning" and metadata["is_reasoning_model"]:
            score *= boost_value
        elif category_boost == "vision" and metadata["is_vision_capable"]:
            score *= boost_value
        elif matches_category_boost(model_id, category_boost, benchmarks):
            score *= boost_value
    
    # Apply tool preference bonus
    if profile_config.get("prefer_tools") and metadata["has_tools"]:
        score *= 1.05
    
    # Vision profile: heavily penalize non-vision models
    if profile_config.get("require_vision") and not metadata["is_vision_capable"]:
        score *= 0.1
    
    # Penalize models below minimum context requirement
    min_context = profile_config.get("min_context", 0)
    if metadata["context_length"] < min_context:
        score *= 0.8
    
    return score


def rank_free_models(models: list, profile: str = "general") -> list:
    """Rank free models by quality score for a given profile."""
    benchmarks = load_benchmarks()
    scored_models = []
    
    for model in models:
        model_id = model.get("id", "")
        
        # Mark routers separately (don't exclude, but flag them)
        is_router = is_router_model(model_id, benchmarks)
        
        score = calculate_model_score(model, profile, benchmarks)
        metadata = parse_model_metadata(model)
        
        scored_models.append({
            **model,
            "_score": score,
            "_profile": profile,
            "_tier": get_benchmark_tier(model_id, benchmarks),
            "_is_router": is_router,
            "_metadata": metadata
        })

    # Sort by score descending
    scored_models.sort(key=lambda x: x["_score"], reverse=True)
    return scored_models


def get_cached_models() -> Optional[list]:
    """Get cached model list if still valid."""
    if not CACHE_FILE.exists():
        return None

    try:
        cache = json.loads(CACHE_FILE.read_text())
        cached_at = datetime.fromisoformat(cache.get("cached_at", ""))
        if datetime.now() - cached_at < timedelta(hours=CACHE_DURATION_HOURS):
            return cache.get("models", [])
    except (json.JSONDecodeError, ValueError):
        pass

    return None


def save_models_cache(models: list):
    """Save models to cache file."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cache = {
        "cached_at": datetime.now().isoformat(),
        "models": models
    }
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def get_free_models(api_key: str, force_refresh: bool = False, profile: str = "general") -> list:
    """Get ranked free models (from cache or API).
    
    Note: Cache stores raw model data. Ranking is applied fresh each time
    based on the requested profile.
    """
    cached = None
    if not force_refresh:
        cached = get_cached_models()
    
    if cached:
        # Re-rank cached models with current profile
        return rank_free_models(cached, profile)
    
    all_models = fetch_all_models(api_key)
    free_models = filter_free_models(all_models)
    
    # Cache the unranked models (so we can re-rank with different profiles)
    save_models_cache(free_models)
    
    # Return ranked by profile
    return rank_free_models(free_models, profile)


def load_openclaw_config() -> dict:
    """Load OpenClaw configuration."""
    if not OPENCLAW_CONFIG_PATH.exists():
        return {}

    try:
        return json.loads(OPENCLAW_CONFIG_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def save_openclaw_config(config: dict):
    """Save OpenClaw configuration."""
    OPENCLAW_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENCLAW_CONFIG_PATH.write_text(json.dumps(config, indent=2))


def format_model_for_openclaw(model_id: str) -> str:
    """Format model ID for OpenClaw config.

    OpenClaw requires the full provider path for all models:
    - "openrouter/<author>/<model>:free" for regular models
    - "openrouter/openrouter/free" for the OpenRouter smart router
    
    The model_id from OpenRouter API is like "qwen/qwen3-coder:free" or "openrouter/free".
    We need to prepend "openrouter/" routing prefix for OpenClaw.
    """
    # Handle openrouter/free special case: "openrouter" is both the routing 
    # prefix AND the actual provider name in the API model ID.
    # API returns "openrouter/free" -> OpenClaw needs "openrouter/openrouter/free"
    if model_id in ("openrouter/free", "openrouter/free:free"):
        return "openrouter/openrouter/free"
    
    # If already has the openrouter/ routing prefix, return as-is
    if model_id.startswith("openrouter/"):
        return model_id

    # Add the openrouter/ routing prefix
    return f"openrouter/{model_id}"


def get_current_model(config: dict = None) -> Optional[str]:
    """Get currently configured model in OpenClaw."""
    if config is None:
        config = load_openclaw_config()
    return config.get("agents", {}).get("defaults", {}).get("model", {}).get("primary")


def get_current_fallbacks(config: dict = None) -> list:
    """Get currently configured fallback models."""
    if config is None:
        config = load_openclaw_config()
    return config.get("agents", {}).get("defaults", {}).get("model", {}).get("fallbacks", [])


def ensure_config_structure(config: dict) -> dict:
    """Ensure the config has the required nested structure without overwriting existing values."""
    if "agents" not in config:
        config["agents"] = {}
    if "defaults" not in config["agents"]:
        config["agents"]["defaults"] = {}
    if "model" not in config["agents"]["defaults"]:
        config["agents"]["defaults"]["model"] = {}
    if "models" not in config["agents"]["defaults"]:
        config["agents"]["defaults"]["models"] = {}
    return config


def setup_openrouter_auth(config: dict) -> dict:
    """Set up OpenRouter auth profile if not exists."""
    if "auth" not in config:
        config["auth"] = {}
    if "profiles" not in config["auth"]:
        config["auth"]["profiles"] = {}

    if "openrouter:default" not in config["auth"]["profiles"]:
        config["auth"]["profiles"]["openrouter:default"] = {
            "provider": "openrouter",
            "mode": "api_key"
        }
        print("Added OpenRouter auth profile.")

    return config


def update_model_config(
    model_id: str,
    as_primary: bool = True,
    add_fallbacks: bool = True,
    fallback_count: int = 5,
    setup_auth: bool = False
) -> bool:
    """Update OpenClaw config with the specified model.

    Args:
        model_id: The model ID to configure
        as_primary: If True, set as primary model. If False, only add to fallbacks.
        add_fallbacks: If True, also configure fallback models
        fallback_count: Number of fallback models to add
        setup_auth: If True, also set up OpenRouter auth profile
    """
    config = load_openclaw_config()
    config = ensure_config_structure(config)

    if setup_auth:
        config = setup_openrouter_auth(config)

    formatted_model = format_model_for_openclaw(model_id)

    if as_primary:
        # Set as primary model (full openrouter/ path)
        config["agents"]["defaults"]["model"]["primary"] = formatted_model
        # Add to models allowlist (also full path)
        config["agents"]["defaults"]["models"][formatted_model] = {}

    # Handle fallbacks
    if add_fallbacks:
        api_key = get_api_key()
        if api_key:
            free_models = get_free_models(api_key)

            # Build new fallbacks list
            new_fallbacks = []

            # Always add openrouter/openrouter/free as first fallback (smart router)
            # Skip if it's being set as primary
            free_router = format_model_for_openclaw("openrouter/free")  # -> openrouter/openrouter/free
            if formatted_model != free_router:
                new_fallbacks.append(free_router)
                config["agents"]["defaults"]["models"][free_router] = {}

            for m in free_models:
                if len(new_fallbacks) >= fallback_count:
                    break

                m_formatted = format_model_for_openclaw(m["id"])

                # Skip openrouter/free (already added as first)
                if "openrouter/free" in m["id"]:
                    continue

                # Skip if it's the new primary
                if as_primary and m_formatted == formatted_model:
                    continue

                # Skip if it's the current primary (when adding to fallbacks only)
                current_primary = config["agents"]["defaults"]["model"].get("primary", "")
                if not as_primary and m_formatted == current_primary:
                    continue

                new_fallbacks.append(m_formatted)
                config["agents"]["defaults"]["models"][m_formatted] = {}

            # If not setting as primary, prepend new model to fallbacks (after openrouter/free)
            if not as_primary:
                if formatted_model not in new_fallbacks:
                    # Insert after openrouter/free if present
                    insert_pos = 1 if free_router in new_fallbacks else 0
                    new_fallbacks.insert(insert_pos, formatted_model)
                config["agents"]["defaults"]["models"][formatted_model] = {}

            config["agents"]["defaults"]["model"]["fallbacks"] = new_fallbacks

    save_openclaw_config(config)
    return True


# ============== Command Handlers ==============

def cmd_list(args):
    """List available free models ranked by quality."""
    api_key = get_api_key()
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set")
        print("Set it via: export OPENROUTER_API_KEY='sk-or-...'")
        print("Or get a free key at: https://openrouter.ai/keys")
        sys.exit(1)

    profile = getattr(args, 'profile', DEFAULT_PROFILE)
    profile_config = get_profile(profile)
    
    print(f"Fetching free models from OpenRouter...")
    print(f"Profile: {profile} - {profile_config['description']}")
    
    models = get_free_models(api_key, force_refresh=args.refresh, profile=profile)

    if not models:
        print("No free models available.")
        return

    current = get_current_model()
    fallbacks = get_current_fallbacks()
    limit = args.limit if args.limit else 15

    print(f"\nTop {min(limit, len(models))} Free AI Models (ranked for '{profile}'):\n")
    print(f"{'#':<3} {'Model ID':<45} {'Tier':<5} {'Context':<10} {'Score':<7} {'Status'}")
    print("-" * 95)

    for i, model in enumerate(models[:limit], 1):
        model_id = model.get("id", "unknown")
        context = model.get("context_length", 0)
        score = model.get("_score", 0)
        tier = model.get("_tier", "?")
        is_router = model.get("_is_router", False)

        # Format context length
        if context >= 1_000_000:
            context_str = f"{context // 1_000_000}M"
        elif context >= 1_000:
            context_str = f"{context // 1_000}K"
        else:
            context_str = f"{context}"

        # Check status
        formatted = format_model_for_openclaw(model_id)

        status_parts = []
        if current and formatted == current:
            status_parts.append("PRIMARY")
        elif formatted in fallbacks:
            status_parts.append("FALLBACK")
        if is_router:
            status_parts.append("ROUTER")
        
        status = f"[{','.join(status_parts)}]" if status_parts else ""

        print(f"{i:<3} {model_id:<45} {tier:<5} {context_str:<10} {score:.3f}   {status}")

    if len(models) > limit:
        print(f"\n... and {len(models) - limit} more. Use --limit to see more.")

    print(f"\nTotal free models available: {len(models)}")
    print(f"\nProfiles: {', '.join(VALID_PROFILES)}")
    print("\nCommands:")
    print(f"  freeride list --profile <profile>   Rank for specific use case")
    print(f"  freeride switch <model>             Set as primary model")
    print(f"  freeride auto --profile {profile}       Auto-select best for {profile}")


def cmd_switch(args):
    """Switch to a specific free model."""
    api_key = get_api_key()
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set")
        sys.exit(1)

    profile = getattr(args, 'profile', DEFAULT_PROFILE)
    model_id = args.model
    as_fallback = args.fallback_only

    # Validate model exists and is free
    models = get_free_models(api_key, profile=profile)
    model_ids = [m["id"] for m in models]

    # Check for exact match or partial match
    matched_model = None
    if model_id in model_ids:
        matched_model = model_id
    else:
        # Try partial match
        for m_id in model_ids:
            if model_id.lower() in m_id.lower():
                matched_model = m_id
                break

    if not matched_model:
        print(f"Error: Model '{model_id}' not found in free models list.")
        print("Use 'freeride list' to see available models.")
        sys.exit(1)

    if as_fallback:
        print(f"Adding to fallbacks: {matched_model}")
    else:
        print(f"Setting as primary: {matched_model}")

    if update_model_config(
        matched_model,
        as_primary=not as_fallback,
        add_fallbacks=not args.no_fallbacks,
        setup_auth=args.setup_auth
    ):
        config = load_openclaw_config()

        if as_fallback:
            print("Success! Added to fallbacks.")
            print(f"Primary model (unchanged): {get_current_model(config)}")
        else:
            print("Success! OpenClaw config updated.")
            print(f"Primary model: {get_current_model(config)}")

        fallbacks = get_current_fallbacks(config)
        if fallbacks:
            print(f"Fallback models ({len(fallbacks)}):")
            for fb in fallbacks[:5]:
                print(f"  - {fb}")
            if len(fallbacks) > 5:
                print(f"  ... and {len(fallbacks) - 5} more")

        print("\nRestart OpenClaw for changes to take effect.")
    else:
        print("Error: Failed to update OpenClaw config.")
        sys.exit(1)


def cmd_auto(args):
    """Automatically select the best free model."""
    api_key = get_api_key()
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set")
        sys.exit(1)

    profile = getattr(args, 'profile', DEFAULT_PROFILE)
    profile_config = get_profile(profile)
    
    config = load_openclaw_config()
    current_primary = get_current_model(config)

    print(f"Finding best free model for '{profile}' profile...")
    print(f"  {profile_config['description']}")
    
    models = get_free_models(api_key, force_refresh=True, profile=profile)

    if not models:
        print("Error: No free models available.")
        sys.exit(1)

    # Find best SPECIFIC model (skip routers)
    best_model = None
    for m in models:
        if not m.get("_is_router", False):
            best_model = m
            break

    if not best_model:
        # Fallback to first model if all are routers (unlikely)
        best_model = models[0]

    model_id = best_model["id"]
    context = best_model.get("context_length", 0)
    score = best_model.get("_score", 0)
    tier = best_model.get("_tier", "?")
    metadata = best_model.get("_metadata", {})

    # Determine if we should change primary or just add fallbacks
    as_fallback = args.fallback_only

    if not as_fallback:
        if current_primary:
            print(f"\nReplacing current primary: {current_primary}")
        print(f"\nBest free model for '{profile}': {model_id}")
        print(f"  Tier: {tier}")
        print(f"  Context: {context:,} tokens")
        print(f"  Score: {score:.3f}")
        if metadata.get("size_billions"):
            print(f"  Size: {metadata['size_billions']}B parameters")
    else:
        print(f"\nKeeping current primary, adding fallbacks only.")
        print(f"Best available: {model_id} (Tier {tier}, score: {score:.3f})")

    if update_model_config(
        model_id,
        as_primary=not as_fallback,
        add_fallbacks=True,
        fallback_count=args.fallback_count,
        setup_auth=args.setup_auth
    ):
        config = load_openclaw_config()

        if as_fallback:
            print("\nFallbacks configured!")
            print(f"Primary (unchanged): {get_current_model(config)}")
            print("First fallback: openrouter/free (smart router - auto-selects best available)")
        else:
            print("\nOpenClaw config updated!")
            print(f"Primary: {get_current_model(config)}")

        fallbacks = get_current_fallbacks(config)
        if fallbacks:
            print(f"Fallbacks ({len(fallbacks)}):")
            for fb in fallbacks:
                print(f"  - {fb}")

        print("\nRestart OpenClaw for changes to take effect.")
    else:
        print("Error: Failed to update config.")
        sys.exit(1)


def cmd_status(args):
    """Show current configuration status."""
    api_key = get_api_key()
    config = load_openclaw_config()
    current = get_current_model(config)
    fallbacks = get_current_fallbacks(config)

    print("FreeRide Status")
    print("=" * 50)

    # API Key status
    if api_key:
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"OpenRouter API Key: {masked}")
    else:
        print("OpenRouter API Key: NOT SET")
        print("  Set with: export OPENROUTER_API_KEY='sk-or-...'")

    # Auth profile status
    auth_profiles = config.get("auth", {}).get("profiles", {})
    if "openrouter:default" in auth_profiles:
        print("OpenRouter Auth Profile: Configured")
    else:
        print("OpenRouter Auth Profile: Not set (use --setup-auth to add)")

    # Current model
    print(f"\nPrimary Model: {current or 'Not configured'}")

    # Fallbacks
    if fallbacks:
        print(f"Fallback Models ({len(fallbacks)}):")
        for fb in fallbacks:
            print(f"  - {fb}")
    else:
        print("Fallback Models: None configured")

    # Cache status
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text())
            cached_at = datetime.fromisoformat(cache.get("cached_at", ""))
            models_count = len(cache.get("models", []))
            age = datetime.now() - cached_at
            hours = age.seconds // 3600
            mins = (age.seconds % 3600) // 60
            print(f"\nModel Cache: {models_count} models (updated {hours}h {mins}m ago)")
        except:
            print("\nModel Cache: Invalid")
    else:
        print("\nModel Cache: Not created yet")

    # OpenClaw config path
    print(f"\nOpenClaw Config: {OPENCLAW_CONFIG_PATH}")
    print(f"  Exists: {'Yes' if OPENCLAW_CONFIG_PATH.exists() else 'No'}")


def cmd_refresh(args):
    """Force refresh the model cache."""
    api_key = get_api_key()
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set")
        sys.exit(1)

    print("Refreshing free models cache...")
    models = get_free_models(api_key, force_refresh=True)
    print(f"Cached {len(models)} free models.")
    print(f"Cache expires in {CACHE_DURATION_HOURS} hours.")


def cmd_fallbacks(args):
    """Configure fallback models for rate limit handling."""
    api_key = get_api_key()
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set")
        sys.exit(1)

    profile = getattr(args, 'profile', DEFAULT_PROFILE)
    config = load_openclaw_config()
    current = get_current_model(config)

    if not current:
        print("Warning: No primary model configured.")
        print("Fallbacks will still be added.")

    print(f"Current primary: {current or 'None'}")
    print(f"Setting up {args.count} fallback models (ranked for '{profile}')...")

    models = get_free_models(api_key, profile=profile)
    config = ensure_config_structure(config)

    # Get fallbacks excluding current model
    fallbacks = []

    # Always add openrouter/openrouter/free as first fallback (smart router)
    free_router = format_model_for_openclaw("openrouter/free")  # -> openrouter/openrouter/free
    if not current or current != free_router:
        fallbacks.append(free_router)
        config["agents"]["defaults"]["models"][free_router] = {}

    for m in models:
        formatted = format_model_for_openclaw(m["id"])

        if current and formatted == current:
            continue
        # Skip openrouter/free (already added as first)
        if "openrouter/free" in m["id"]:
            continue
        if len(fallbacks) >= args.count:
            break

        fallbacks.append(formatted)
        config["agents"]["defaults"]["models"][formatted] = {}

    config["agents"]["defaults"]["model"]["fallbacks"] = fallbacks
    save_openclaw_config(config)

    print(f"\nConfigured {len(fallbacks)} fallback models:")
    for i, fb in enumerate(fallbacks, 1):
        print(f"  {i}. {fb}")

    print("\nWhen rate limited, OpenClaw will automatically try these models.")
    print("Restart OpenClaw for changes to take effect.")


def cmd_benchmarks(args):
    """Show or manage benchmark data."""
    benchmarks = load_benchmarks()
    
    if not benchmarks:
        print("Error: benchmarks.json not found or invalid.")
        print(f"Expected at: {BENCHMARKS_FILE}")
        sys.exit(1)
    
    print("FreeRide Benchmark Data")
    print("=" * 60)
    print(f"Version: {benchmarks.get('version', 'unknown')}")
    print(f"Last updated: {benchmarks.get('last_updated', 'unknown')}")
    print(f"Description: {benchmarks.get('description', 'N/A')}")
    
    print("\nQuality Tiers:")
    tiers = benchmarks.get("tiers", {})
    for tier_name in ["S", "A", "B", "C"]:
        tier_data = tiers.get(tier_name, {})
        score = tier_data.get("score", "?")
        patterns = tier_data.get("patterns", [])
        print(f"\n  Tier {tier_name} (score: {score}):")
        print(f"    {tier_data.get('description', 'N/A')}")
        if patterns:
            print(f"    Patterns: {', '.join(patterns[:5])}")
            if len(patterns) > 5:
                print(f"              ... and {len(patterns) - 5} more")
    
    print("\nCategory Boosts:")
    boosts = benchmarks.get("category_boosts", {})
    for cat, data in boosts.items():
        boost = data.get("boost", 1.0)
        patterns = data.get("patterns", [])
        print(f"  {cat}: {boost}x boost")
        print(f"    Patterns: {', '.join(patterns[:3])}")
    
    print("\nRouters (excluded from primary selection):")
    routers = benchmarks.get("routers", {})
    for pattern in routers.get("patterns", []):
        print(f"  - {pattern}")
    
    print(f"\nBenchmarks file: {BENCHMARKS_FILE}")


def main():
    parser = argparse.ArgumentParser(
        prog="freeride",
        description="FreeRide - Free AI for OpenClaw. Manage free models from OpenRouter."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Common profile argument helper
    profile_help = f"Use-case profile for ranking. Options: {', '.join(VALID_PROFILES)} (default: {DEFAULT_PROFILE})"

    # list command
    list_parser = subparsers.add_parser("list", help="List available free models")
    list_parser.add_argument("--limit", "-n", type=int, default=15,
                            help="Number of models to show (default: 15)")
    list_parser.add_argument("--refresh", "-r", action="store_true",
                            help="Force refresh from API (ignore cache)")
    list_parser.add_argument("--profile", "-p", type=str, default=DEFAULT_PROFILE,
                            choices=VALID_PROFILES, help=profile_help)

    # switch command
    switch_parser = subparsers.add_parser("switch", help="Switch to a specific model")
    switch_parser.add_argument("model", help="Model ID to switch to")
    switch_parser.add_argument("--fallback-only", "-f", action="store_true",
                              help="Add to fallbacks only, don't change primary")
    switch_parser.add_argument("--no-fallbacks", action="store_true",
                              help="Don't configure fallback models")
    switch_parser.add_argument("--setup-auth", action="store_true",
                              help="Also set up OpenRouter auth profile")
    switch_parser.add_argument("--profile", "-p", type=str, default=DEFAULT_PROFILE,
                              choices=VALID_PROFILES, help=profile_help)

    # auto command
    auto_parser = subparsers.add_parser("auto", help="Auto-select best free model")
    auto_parser.add_argument("--fallback-count", "-c", type=int, default=5,
                            help="Number of fallback models (default: 5)")
    auto_parser.add_argument("--fallback-only", "-f", action="store_true",
                            help="Add to fallbacks only, don't change primary")
    auto_parser.add_argument("--setup-auth", action="store_true",
                            help="Also set up OpenRouter auth profile")
    auto_parser.add_argument("--profile", "-p", type=str, default=DEFAULT_PROFILE,
                            choices=VALID_PROFILES, help=profile_help)

    # status command
    subparsers.add_parser("status", help="Show current configuration")

    # refresh command
    subparsers.add_parser("refresh", help="Refresh model cache")

    # fallbacks command
    fallbacks_parser = subparsers.add_parser("fallbacks", help="Configure fallback models")
    fallbacks_parser.add_argument("--count", "-c", type=int, default=5,
                                 help="Number of fallback models (default: 5)")
    fallbacks_parser.add_argument("--profile", "-p", type=str, default=DEFAULT_PROFILE,
                                 choices=VALID_PROFILES, help=profile_help)

    # benchmarks command
    subparsers.add_parser("benchmarks", help="Show benchmark data and quality tiers")

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args)
    elif args.command == "switch":
        cmd_switch(args)
    elif args.command == "auto":
        cmd_auto(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "refresh":
        cmd_refresh(args)
    elif args.command == "fallbacks":
        cmd_fallbacks(args)
    elif args.command == "benchmarks":
        cmd_benchmarks(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()