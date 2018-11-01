2. External Javascript Integration As Webworker
--------------------------------

Status
------

Draft

Context
-------

We need to clarify a Javascript API through which integrators can
respond to certain Learner-flow events in the course of taking a
proctored exam. We may have needs in the future to allow integrators
some degree of flexibility in what they use, but will need to balance
that against security concerns.

Decision
--------

We will proceed to allow integrators to provide javascript code which
will be integrated into our systems as follows:

1. Externally provided source code will be isolated from JS that
   controls our page using a WebWorker_
2. Their Javascript will be provided as an ES6 module.
.. _`number 3`:
3. Content security policy will be limited such that the WebWorker
   cannot load additional Javascript.

Consequences
------------

TBD

Open Questions
--------------

This Architecture Decision Record will need to remain in draft state
until the following can be investigated:

1. Does the `worker-src`_ ``Content-Security-Policy`` directive
   suffice to satisfy `number 3`_.?
2. What tooling is available to enforce that our proctoring providers
   satisfy our WebWorker requirement? Are Javascript interfaces
   sufficient for this need, or is this feature too immature?


References
----------

.. target-notes::

.. _WebWorker: https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API
.. _worker-src: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/worker-src
