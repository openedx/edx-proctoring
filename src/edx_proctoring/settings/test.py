"Pluggable Django App settings for test"


def plugin_settings(settings):
    "Injects local settings into django settings"
    settings.PROCTORING_SETTINGS = {}
    settings.PROCTORING_BACKENDS = {
        'DEFAULT': 'mock',
        'mock': {},
        'mock_proctoring_without_rules': {}
    }
