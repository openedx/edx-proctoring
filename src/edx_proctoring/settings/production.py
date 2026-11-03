"Pluggable Django App settings for production"


def plugin_settings(settings):
    "Injects local settings into django settings"
    auth_tokens = getattr(settings, 'AUTH_TOKENS', {})
    env_tokens = getattr(settings, 'ENV_TOKENS', {})
    if env_tokens.get('PROCTORING_SETTINGS'):
        settings.PROCTORING_SETTINGS = env_tokens['PROCTORING_SETTINGS']
    if auth_tokens.get('PROCTORING_BACKENDS'):
        settings.PROCTORING_BACKENDS = auth_tokens['PROCTORING_BACKENDS']
    elif env_tokens.get('PROCTORING_BACKENDS'):
        settings.PROCTORING_BACKENDS = env_tokens['PROCTORING_BACKENDS']
