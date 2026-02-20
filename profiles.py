"""
FreeRide Profiles - Use-case specific ranking configurations.

Each profile defines weights for different scoring factors and
specifies which category boosts to apply.
"""

PROFILES = {
    "coding": {
        "description": "Optimized for code generation, completion, and understanding",
        "weights": {
            "benchmark": 0.35,
            "size": 0.25,
            "context": 0.25,
            "capability": 0.15
        },
        "category_boost": "coding",
        "prefer_tools": True,
        "min_context": 32000
    },
    "reasoning": {
        "description": "Optimized for complex reasoning, analysis, and problem-solving",
        "weights": {
            "benchmark": 0.40,
            "size": 0.30,
            "context": 0.20,
            "capability": 0.10
        },
        "category_boost": "reasoning",
        "prefer_tools": False,
        "min_context": 16000
    },
    "general": {
        "description": "Balanced profile for general-purpose chat and assistance",
        "weights": {
            "benchmark": 0.45,
            "size": 0.25,
            "context": 0.20,
            "capability": 0.10
        },
        "category_boost": None,
        "prefer_tools": True,
        "min_context": 8000
    },
    "vision": {
        "description": "Optimized for image understanding and multimodal tasks",
        "weights": {
            "benchmark": 0.30,
            "size": 0.20,
            "context": 0.20,
            "capability": 0.30
        },
        "category_boost": "vision",
        "prefer_tools": False,
        "min_context": 8000,
        "require_vision": True
    }
}

DEFAULT_PROFILE = "general"

VALID_PROFILES = list(PROFILES.keys())


def get_profile(name: str) -> dict:
    """Get a profile by name, falling back to default if not found."""
    return PROFILES.get(name, PROFILES[DEFAULT_PROFILE])


def get_profile_weights(name: str) -> dict:
    """Get the scoring weights for a profile."""
    return get_profile(name)["weights"]


def get_profile_description(name: str) -> str:
    """Get the description for a profile."""
    return get_profile(name)["description"]


def list_profiles() -> list:
    """Return list of all available profile names."""
    return VALID_PROFILES.copy()
