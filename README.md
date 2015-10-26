edx-proctoring [![Build Status](https://travis-ci.org/edx/edx-proctoring.svg?branch=master)](https://travis-ci.org/edx/edx-proctoring) [![Coverage Status](https://coveralls.io/repos/edx/edx-proctoring/badge.svg?branch=master&service=github)](https://coveralls.io/github/edx/edx-proctoring?branch=master)

========================

This is the Exam Proctoring subsystem for the Open edX platform.


While technical and developer documentation is forthcoming, here are basic instructions on how to use this
in an Open edX installation.

NOTE: Proctoring will not be available in the Open edX named releases until Dogwood. However, you can use this if you use a copy of edx-platform (master) after 8/20/2015.

In order to use edx-proctoring, you must obtain an account (and secret configuration - see below) with SoftwareSecure, which provides the proctoring review services that edx-proctoring integrates with.


CONFIGURATION:

You will need to turn on the ENABLE_SPECIAL_EXAMS in lms.env.json and cms.env.json FEATURES dictionary:

```
:
"FEATURES": {
    :
    "ENABLE_SPECIAL_EXAMS": true,
    :
}
```

Also in your lms.env.json and cms.env.json file you can add the following (optional):

```
    "PROCTORING_SETTINGS": {
        "ALLOW_CALLBACK_SIMULATION": False,
        "CLIENT_TIMEOUT": 30,
        "DEFAULT_REVIEW_POLICY": "Closed Book",
        "REQUIRE_FAILURE_SECOND_REVIEWS": False
    },
```
**Note** Settings for each provider moved to its PROCTORING_BACKEND_PROVIDERS's `settings`. See below.

In your lms.auth.json file, please add the following *secure* information:

```
    "PROCTORING_BACKEND_PROVIDERS":{
        "SOFTWARE_SECURE": {
            "class": "edx_proctoring.backends.software_secure.SoftwareSecureBackendProvider",
            "options": {
                "crypto_key": "{add SoftwareSecure crypto key here}",
                "exam_register_endpoint": "{add enpoint to SoftwareSecure}",
                "exam_sponsor": "{add SoftwareSecure sponsor}",
                "organization": "{add SoftwareSecure organization}",
                "secret_key": "{add SoftwareSecure secret key}",
                "secret_key_id": "{add SoftwareSecure secret key id}",
                "software_download_url": "{add SoftwareSecure download url}"
            },
            "settings": {
                "LINK_URLS": {
                    "contact_us": "{add link here}",
                    "faq": "{add link here}",
                    "online_proctoring_rules": "{add link here}",
                    "tech_requirements": "{add link here}"
                }            
            }
        },
        "WEB_ASSISTANT": {
            "class": "lms.djangoapps.AnyBackendProvider",
            "options": {
                "crypto_key": "{add crypto key}",
                "exam_register_endpoint": "{add enpoint to WebAssistant}",
                "exam_sponsor": "{add sponsor}",
                "organization": "{add organization}",
                "secret_key": "{add secret key}",
                "secret_key_id": "{add secret key id}",
                "software_download_url": "{add software download url}"
            },
            "settings": {
                "SITE_NAME": "{add site name here}",
                "PLATFORM_NAME": "{add platform name here}",
                "STATUS_EMAIL_FROM_ADDRESS": "{add email address here}",
                "CONTACT_EMAIL": "{add email address here}",
                "DEFAULT_REVIEW_POLICY":"{add policy here}",
                "REQUIRE_FAILURE_SECOND_REVIEWS":"{add policy here}",
                "ALLOW_REVIEW_UPDATES": false,
                "LINK_URLS": {
                    "contact_us": "{add link here}",
                    "faq": "{add link here}",
                    "online_proctoring_rules": "{add link here}",
                    "tech_requirements": "{add link here}"
                }            
            }            
        }
    },
```

You will need to restart services after these configuration changes for them to take effect.
