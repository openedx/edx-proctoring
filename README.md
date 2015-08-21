edx-proctoring [![Build Status](https://travis-ci.org/edx/edx-proctoring.svg?branch=master)](https://travis-ci.org/edx/edx-proctoring) [![Coverage Status](https://coveralls.io/repos/edx/edx-proctoring/badge.svg?branch=master&service=github)](https://coveralls.io/github/edx/edx-proctoring?branch=master)

========================

This is the Exam Proctoring subsystem for the Open edX platform.


While technical and developer documentation is forthcoming, here are basic instructions on how to use this
in an Open edX installation.

NOTE: Proctoring will not be available in the Open edX named releases until Dogwood. However, you can use this if you use a copy of edx-platform (master) after 8/20/2015.

In order to use edx-proctoring, you must obtain an account (and secret configuration - see below) with SoftwareSecure, which provide the proctoring review services that edx-proctoring integrates with.


CONFIGURATION:

You will need to turn on the ENABLE_PROCTORED_EXAMS in lms.env.json and cms.env.json FEATURES dictionary:

```
:
"FEATURES": {
    :
    "ENABLE_PROCTORED_EXAMS": true,
    :
}
```

Also in your lms.env.json and cms.env.json file please add the following:

```
    "PROCTORING_SETTINGS": {
        "LINK_URLS": {
            "contact_us": "{add link here}",
            "faq": "{add link here}",
            "online_proctoring_rules": "{add link here}",
            "tech_requirements": "{add link here}"
        }
    },
```

In your lms.auth.json file, please add the following *secure* information:

```
    "PROCTORING_BACKEND_PROVIDER": {
        "class": "edx_proctoring.backends.software_secure.SoftwareSecureBackendProvider",
        "options": {
            "crypto_key": "{add SoftwareSecure crypto key here}",
            "exam_register_endpoint": "{add enpoint to SoftwareSecure}",
            "exam_sponsor": "{add SoftwareSecure sponsor}",
            "organization": "{add SoftwareSecure organization}",
            "secret_key": "{add SoftwareSecure secret key}",
            "secret_key_id": "{add SoftwareSecure secret key id}",
            "software_download_url": "{add SoftwareSecure download url}"
        }
    },
```

You will need to restart services after these configuration changes for them to take effect.
