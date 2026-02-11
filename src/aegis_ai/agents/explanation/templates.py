"""Explanation templates - separated for maintainability."""

TEMPLATES = {
    "new_device": "This login is from a new device not previously associated with this account.",
    "new_location": "This login originates from a new geographic location.",
    "new_ip": "This login is from a new IP address.",
    "behavioral_deviation": "This session deviates from the user's typical behavioral patterns.",
    "network_risk": "Network analysis indicates shared infrastructure with other accounts.",
    "time_anomaly": "This login occurred outside the user's typical hours.",
    "vpn_tor": "This connection uses anonymization technology.",
    "high_velocity": "Multiple login attempts were detected in a short period.",
    "low_confidence": "Due to uncertainty in the analysis, additional verification is recommended.",
    "agent_disagreement": "Analysis signals show conflicting indicators.",
}

ACTION_TEMPLATES = {
    "allow": "No additional verification required. Login may proceed.",
    "challenge": "Additional verification is recommended before allowing access.",
    "escalate": "This case requires human review before proceeding.",
    "block": "Access should be temporarily blocked pending verification.",
}

FEATURE_DESCRIPTIONS = {
    "is_new_device": "First-time device increases risk",
    "device_not_known": "Unknown device increases risk",
    "is_new_ip": "New IP address increases risk",
    "is_new_location": "Login from new geographic location increases risk",
    "is_vpn": "VPN usage increases risk",
    "is_tor": "Tor network usage significantly increases risk",
    "failed_attempts_before": "Failed login attempts before this session",
    "failed_attempts_capped": "High number of failed attempts detected",
    "time_since_last_login_hours": "Time since last login",
    "is_long_absence": "Extended absence from account increases risk",
    "auth_method_password": "Password authentication used",
    "auth_method_mfa": "Multi-factor authentication used",
    "auth_method_sso": "Single sign-on authentication used",
    "auth_method_biometric": "Biometric authentication used",
}

BEHAVIORAL_DESCRIPTIONS = {
    "time": "Login time differs from typical pattern",
    "device": "Device usage differs from typical pattern",
    "browser": "Browser usage differs from typical pattern",
    "location": "Login location differs from typical pattern",
    "velocity": "Login frequency differs from typical pattern",
}
