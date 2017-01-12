#Special Exams

## edx-proctoring [![Build Status](https://travis-ci.org/edx/edx-proctoring.svg?branch=master)](https://travis-ci.org/edx/edx-proctoring) [![Coverage Status](https://coveralls.io/repos/edx/edx-proctoring/badge.svg?branch=master&service=github)](https://coveralls.io/github/edx/edx-proctoring?branch=master)

[User docs - Proctored Exams](http://edx.readthedocs.io/projects/edx-partner-course-staff/en/latest/course_features/credit_courses/proctored_exams.html)

[User docs - Timed Exams](http://edx.readthedocs.io/projects/edx-partner-course-staff/en/latest/course_features/timed_exams.html)

## Description:

This is the Exam Proctoring subsystem for the Open edX platform.

## Configuration:

You will need to turn on the ENABLE_SPECIAL_EXAMS in lms.env.json and cms.env.json FEATURES dictionary:

```
    "FEATURES": {
        :
        "ENABLE_SPECIAL_EXAMS": true,
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


## Installation

The intent of this project is to be installed as Django apps that will be included in `edx-platform <https://github.com/edx/edx-platform>`_.

Clone the repo:

```
    mkdir proctoring
    cd proctoring
    git clone git@github.com:Edraak/edx-proctoring.git
```

Create the Virtual Environment:

```
    mkvirtualenv development
    workon development
```

To install all dependencies:

```
    make install-sys-requirements
    make install
    make install-dev
```

## Running Tests

To run all python unit tests:

```
    make test
```

To run just the JavaScript tests:

```
    gulp test
```

## i18n

You will need to:

1. Install [i18n-tools](https://github.com/edx/i18n-tools)

    ```
        pip install git+git://github.com/edx/i18n-tools
    ```

2. Configure Transifex, as described in the [docs](http://docs.transifex.com/developer/client/setup)
3. Install [gettext](http://www.gnu.org/software/gettext/)

To extract strings and push to Transifex

```
    make i18n-push
```

To pull strings from Transifex

```
    make i18n-pull
```