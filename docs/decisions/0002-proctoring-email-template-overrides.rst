Proctoring Email Template Overrides
-----------------------------------

Status
------

Accepted

Context
-------

edX sends email(s) to a learner with the status of their proctored exam attempt after the learner
has submitted their proctored exam. The content(s) of these emails is specified by `email templates`_
in the edx-proctoring repository. These emails may include contact information in the event that a learner
has further questions about their proctored exam status.

.. _`email templates`: https://github.com/openedx/edx-proctoring/tree/master/edx_proctoring/templates/emails

Proctoring services are provided by edX by integrating with third-party proctoring solutions.

Depending on the proctoring provider used for a proctored exam, the contents of an email sent to a learner may need to contain provider specific information, such as contact information, or have a different structure.

Much of the provider specific configuration and behavior is specified in a lightweight plugin that hooks into the edx-proctoring subsystem.

Decision
--------

- We will leverage Django's template override system and template inheritance to provide the ability to override either the entire email template or specific blocks of the template.

- We will create overriding or extending templates in the application that installs edx-proctoring as a subsystem. In our case, this is edx-platform.

- We will create an overriding or extending template in edx-platform at the following path: ``emails/proctoring/{backend}/{template_name}``, where backend specifies the name of the ``proctoring provider`` and ``template_name`` is the name of the base template in edx-proctoring.

- We will not perform overrides or specify customizations to email templates within the proctoring provider plugin, where much of the proctoring provider specific behavior is implemented. This is to provide greater flexibility and control over emails that the edX system sends to learners.


Consequences
------------

- Although proctoring provider specific changes to email templates can be considered proctoring provider specific configuration, we will not store these templates within the proctoring plugin.
- We will not refer to specific proctoring providers when rendering email templates within the edx-proctoring subsystem.
- We will make modifications to email templates that are specific to a proctoring backend by implementing overrides or extending the base template in the edx-platform emails directory.

References
----------

- `Email Templates in edx-proctoring Subsystem <https://github.com/openedx/edx-proctoring/tree/master/edx_proctoring/templates/emails>`_
- `Code Where We Leverage Django’s Template Override System <https://github.com/openedx/edx-proctoring/blob/c92f2e55a3fa2249e48fb383f53f77b84daefc90/edx_proctoring/api.py#L1144>`_