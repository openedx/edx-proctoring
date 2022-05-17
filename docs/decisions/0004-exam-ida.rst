Exams as an Independently Deployed Application
==============================================

Status
------

Accepted (circa May 2022)

Context
-------
The process to release changes in this library to a production environment is both slow and involves multiple manual steps.
Developers must update version numbers for this library, create a tag, and merge updated requirements to edx-platform to release changes. (`Release Instructions`_)
Waiting for the platform CI checks and deployment pipeline to run can take up to half a day. This adds significant turnaround
to releasing even the smallest of changes.

This led us to evaluate moving this code from an in-platform plugin as it exists today to an entirely separate microservice. Right now this library is tightly coupled with the platform; lacking a well-defined interface, there are many imports in both directions. However, the actual data models contained within this library are entirely specific to proctoring tools and user flow. Historically this code needed to be a plugin because it contains rendering functions that are called directly when the LMS renders exam content. This feature is no longer needed, it has been replaced by the learning MFE and `special-exams-lib`_. In general, the features in this codebase are not needed outside the exam context and the current integration surface could be greatly reduced.

We believe we can create a well-defined interface that results in an exam solution deployed as an IDA (Independently Deployable Application). The following proposed component diagram defines the relationship between platform components and the bounded context of timed exams.

`Exam Components`_

As additional motivation for this effort, we intend to eliminate vendor-specific integration code by implementing the IMS's `Proctoring Services Standard`_ built on top of LTI 1.3. To use this library as it stands we would need to build this as a third type of backend interface while maintaining the two existing backend types. Trying to support all three is just going to add extra engineering effort and complexity. A new IDA gives us a clean starting point to build that interface, and the separation will allow us to more easily deprecate the current integrations.

.. _Proctoring Services Standard: https://www.imsglobal.org/proctoring-services

.. _Exam Components: https://lucid.app/lucidchart/a4b40637-93f1-47f1-bb17-d68e4ff6f9d9/edit?invitationId=inv_92a6d5c4-d14c-472a-b2bc-64b64d9d45ef

.. _Release Instructions: https://github.com/openedx/edx-proctoring/blob/master/docs/developing.rst#how-do-i-release-edx-proctoring

.. _special-exams-lib: https://github.com/edx/frontend-lib-special-exams 

Decision
--------
A new repository and IDA will be created for the exam service. This new exam service will handle all configuration and interaction with third party proctoring tools. It will also be the source of truth for managing a learner's progress through exam setup, completion, and review flows.

* The IDA will function in parallel with the current edx-proctoring library. edx-platform may use either service for a course.

    * Exams should be considered a periphery service. As such, edx-platform should not depend on this service.

* Changes in exam state that would impact other systems such as grades, completion, credit, or certificates should be pushed to those systems via REST endpoints or using events.

* Data about course content or exam configuration will be pushed to the IDA's REST API as part of the studio publish action. We should replicate data instead of reading directly from the CMS or LMS in an ad-hoc manner.

* The IDA will implement a REST API to expose exam and attempt state information to https://github.com/edx/frontend-lib-special-exams.

* The IDA will not include custom APIs or data calls specific to a single proctoring tool.

Consequences
------------

* The display of learner attempt state in course outlines requires the LMS to directly depend on the proctoring service which is undesireable per the decisions made above. This feature will be simplified to only contain information about the type of exam. Attempt state will be accessible within the section via the frontend-lib-special-exams library.

* The LMS will need a new way to prevent rendering exam content when a learner is not eligible to view exam problems that does not rely on the installation of this library.

* Existing proctoring vendors will remain functional using this library but will not by-default be implemented in the new IDA.

* We will need to maintain both proctoring implementations until we can migrate use away from this library and the vendors it specifically supports.

* The IDA will not need to render any html templates, all UI views should be handled by https://github.com/edx/frontend-lib-special-exams. This is a significant amount of the current codebase that does not need to be rebuilt.

References
----------

* Spec Document: https://openedx.atlassian.net/wiki/spaces/PT/pages/3251535873/Independently+Deployable+Special+Exam+Service
