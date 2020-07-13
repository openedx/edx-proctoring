Proctoring System Overview
===========================
This document outlines the components involved in the edX proctoring system. It should
serve as a guide to orient developers on what components exist, how they interact, and 
where to find the source code in our platform.

.. contents::

System Components
------------------

.. image:: images/components.png

Proctored Exam Views
^^^^^^^^^^^^^^^^^^^^

Interstitial views within a section that are shown to in place of the actual
exam content. They are used to walk a leaner through setup steps
and display the state of the current attempt.

The LMS calls into edx-proctoring to load the relevent template when rendering the
`student_view()` for an exam section that is proctored.

LMS: https://github.com/edx/edx-platform/blob/a7dff8c21ee794e90bdc0f22876334a7843a032d/common/lib/xmodule/xmodule/seq_module.py#L274
edx-proctoring: https://github.com/edx/edx-proctoring/blob/78976d93ab6ca5206f259dc420d2f45818fe636c/edx_proctoring/api.py#L1912

Templates for these views are defined in edx-proctoring: https://github.com/edx/edx-proctoring/tree/master/edx_proctoring/templates

JavaScript Message API and Worker
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A set of functions called by edX courseware to emit messages based on changing
exam states. These messages may be handled by a JS worker specific to the proctoring provider. 
That worker is included as part of the the provider's python plugin and will 
interface directly with the proctoring software running on the learner's machine. Exam
state will transition forward only after these messages have been successfully handled.
However if a provider does not have a worker interface configured there will be no direct
communication between edX courseware and the proctoring client.

edX Message API
https://github.com/edx/edx-proctoring/blob/master/edx_proctoring/static/proctoring/js/exam_action_handler.js

(example) Proctortrack worker
https://github.com/joshivj/edx-proctoring-proctortrack/blob/master/edx_proctoring_proctortrack/static/proctortrack_custom.js

edx-proctoring
^^^^^^^^^^^^^^
Python plugin that handles the bulk of edX's proctoring logic. It hosts the models for proctored
exam configuration and learner attempts.  It exposes a REST and Python interface to manage them.
edx-proctoring is also responsible for calling out to the provider's backend (through a plugin) to keep
exam configuration and learner attempts in-sync between the two systems.

provider-specific plugin
^^^^^^^^^^^^^^^^^^^^^^^^
Integration layer to handle making REST/http requests to the provider's backend.
This can exist as a Python module or be hard coded into edx-proctoring as a backend.
More information on configuring backends can be found here: https://github.com/edx/edx-proctoring/blob/master/docs/backends.rst

We have two non-testing backends:
1. Proctortrack: https://github.com/joshivj/edx-proctoring-proctortrack
2. RPNow: https://github.com/edx/edx-proctoring/blob/447c0bf49f31fa4df2aa2b0339137ccfd173f237/edx_proctoring/backends/software_secure.py

For backend testing in a local environment see mockprock in the :doc: `developing.rst`

Exam States and User Flow
--------------------------
When a learner first enters a proctored exam subsection an exam attempt is created
in the edX system. User actions and the proctoring software will update the status of
this attempt. The following diagram describes the user flow through those status
updates.

Note this figure does not include error states or display of unmet prerequite requirements
.. image:: images/attempt_states.png

Example Action Sequence
-------------------------

The diagram below describes the happy-path of interactions between components to 
sucessfully begin a proctored exam.

.. image:: images/sequence.png
