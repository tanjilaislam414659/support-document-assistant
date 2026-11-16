# Saved final evidence and confirmed review

Curated readable view of existing records only. No new inference, retrieval, labels or scores. The original human annotations remain separate; exact supplied evidence and messages are retained in the linked context projections. Controls are not ordinary retrieval successes.

## ordinary


### T01-v1--ordinary

**Question:** Which PowerShell script activates a venv on Windows?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"The PowerShell script to activate a venv on Windows is :samp:`{\u003cvenv\u003e}\\\\Scripts\\\\Activate.ps1`.","citations":["E2-S1"], "status":"answered"}
~~~

**Confirmed human assessment:** Correctness 1. Correct and complete script identification; directly supported citation. Documentation markup is a presentation issue.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T01-v1--ordinary.json).

### T01-v2--ordinary

**Question:** For Windows PowerShell, which activation script belongs to the environment?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"For Windows PowerShell, the activation script is :samp:`PS C:\\\\\u003e {\u003cvenv\u003e}\\\\Scripts\\\\Activate.ps1`.","citations":["E1-S1"], "status":"answered"}
~~~

**Confirmed human assessment:** Correctness 1. Correct and complete script identification; directly supported citation. Copied shell-prompt notation is a presentation issue.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T01-v2--ordinary.json).

### T02-v1--ordinary

**Question:** Will default venv creation install pip, and can I opt out?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"The default virtual environment creation does not install pip, and it is possible to opt out.","citations":["E2-S8","E3-S6"],"status":"answered"}
~~~

**Confirmed human assessment:** Correctness 0. Incorrect pip default and missing --without-pip option. Neither emitted citation supports either pip-default/opt-out claim.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T02-v1--ordinary.json).

### T02-v2--ordinary

**Question:** How can I create a virtual environment without bootstrapping pip?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"A virtual environment may be \"activated\" using a script in its binary directory (``bin`` on POSIX; ``Scripts`` on Windows).","citations":["E1-S3"],"status":"answered"}
~~~

**Confirmed human assessment:** Correctness 0. Nonresponsive activation explanation. The citation supports that statement, but it does not answer the creation question.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T02-v2--ordinary.json).

### T03-v1--ordinary

**Question:** How do I request an exact package version using pip?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"You can request an exact package version by specifying the package name followed by ``==`` and the version number.","citations":["E2-S6","E2-S7","E3-S5"],"status":"answered"}
~~~

**Confirmed human assessment:** Correctness 1. Correct package==version explanation. All three citations support the syntax; redundant but relevant.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T03-v1--ordinary.json).

### T03-v2--ordinary

**Question:** What syntax asks pip for SomePackage version 1.0.4?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"The syntax \"python -m pip install \"SomePackage\u003e=1.0.4\"\" asks pip for SomePackage version 1.0.4.","citations":["E1-S5"],"status":"answered"}
~~~

**Confirmed human assessment:** Correctness 0. Substitutes a minimum-version constraint for exact version. The cited passage contradicts that exact-version interpretation.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T03-v2--ordinary.json).

### T04-v1--ordinary

**Question:** What will the next unreleased Python version change about venv?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"The next unreleased Python version will add the ``--without-scm-ignore-files`` option to the ``venv`` module.","citations":["E3-S5"],"status":"answered"}
~~~

**Confirmed human assessment:** Unsuccessful abstention. Unsupported future-release forecast; inappropriate answered status. Citation describes an existing Python 3.13 change.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T04-v1--ordinary.json).

### T04-v2--ordinary

**Question:** Can you guarantee how venv will behave in the next future Python release?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"The behavior of venv is not guaranteed in future Python releases.","citations":["E1-S2","E1-S3"],"status":"answered"}
~~~

**Confirmed human assessment:** Unsuccessful abstention. Avoids a guarantee but omits the pinned-version boundary and uses answered status. Citations do not support future behavior.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T04-v2--ordinary.json).

### T05-v1--ordinary

**Question:** Which exact NumPy wheel is compatible with my unnamed industrial hardware?

**Application outcome:** validated_insufficient_evidence. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"The exact NumPy wheel compatible with your unnamed industrial hardware is not directly specified in the provided documentation.","citations":[],"status":"insufficient_evidence"}
~~~

**Confirmed human assessment:** Unsuccessful under the frozen abstention checklist. Appropriate missing-information direction but incomplete compatibility-details explanation. Empty citations acceptable.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T05-v1--ordinary.json).

### T05-v2--ordinary

**Question:** Pick the correct binary wheel for my machine without any platform or version details.

**Application outcome:** validated_insufficient_evidence. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"insufficient_evidence","citations":[],"status":"insufficient_evidence"}
~~~

**Confirmed human assessment:** Unsuccessful abstention. Literal label without required explanation or requested details. Empty citations acceptable.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T05-v2--ordinary.json).

## gold evidence control


### T01-v1--gold

**Question:** Which PowerShell script activates a venv on Windows?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"The PowerShell script to activate a venv on Windows is `{\u003cvenv\u003e}\\\\Scripts\\\\Activate.ps1`.","citations":["G1-S1"], "status":"answered"}
~~~

**Confirmed human assessment:** Correctness 1; directly supported; formatting limitation.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T01-v1--gold.json).

### T01-v2--gold

**Question:** For Windows PowerShell, which activation script belongs to the environment?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"For Windows PowerShell, the activation script is :samp:`PS C:\\\\\u003e {\u003cvenv\u003e}\\\\Scripts\\\\Activate.ps1`","citations":["G1-S1"], "status":"answered"}
~~~

**Confirmed human assessment:** Correctness 1; directly supported; formatting limitation.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T01-v2--gold.json).

### T02-v1--gold

**Question:** Will default venv creation install pip, and can I opt out?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"Yes, by default, venv creation will install pip, and you can opt out by using the ``--without-pip`` option.","citations":["G1-S1"],"status":"answered"}
~~~

**Confirmed human assessment:** Correctness 1; both default-pip and opt-out facts supported.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T02-v1--gold.json).

### T02-v2--gold

**Question:** How can I create a virtual environment without bootstrapping pip?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"Use the ``--without-pip`` option when creating the virtual environment.","citations":["G1-S1"],"status":"answered"}
~~~

**Confirmed human assessment:** Correctness 1; --without-pip directly supported.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T02-v2--gold.json).

### T03-v1--gold

**Question:** How do I request an exact package version using pip?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"To request an exact package version using pip, you can specify the version directly on the command line with the ``==`` operator.", "citations":["G1-S1"],"status":"answered"}
~~~

**Confirmed human assessment:** Correctness 0.5; correct operator but incomplete package/version syntax explanation. Stated operator is supported.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T03-v1--gold.json).

### T03-v2--gold

**Question:** What syntax asks pip for SomePackage version 1.0.4?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"The syntax ``python -m pip install SomePackage==1.0.4`` asks pip for SomePackage version 1.0.4.","citations":["G1-S1"],"status":"answered"}
~~~

**Confirmed human assessment:** Correctness 1; specifically requested exact-version command supported.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T03-v2--gold.json).

## genuine evidence plus distractor


### T06-v1--genuine_evidence_plus_distractor

**Question:** Can I move a venv to another folder and count on installed scripts working?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"No, you cannot count on installed scripts working if you move a venv to another folder.","citations":["G1-S1"],"status":"answered"}
~~~

**Confirmed human assessment:** Correctness 0.5. Correct rejection of reliable relocation, but missing absolute-path explanation and recreation guidance. Central claim supported; no visible adoption of the false portability claim.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T06-v1--genuine_evidence_plus_distractor.json).

### T06-v2--genuine_evidence_plus_distractor

**Question:** A copied note says a venv is portable. Should I trust that?

**Application outcome:** validated_answer. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"The copied note is not trustworthy because the evidence shows that environments are inherently non-portable.","citations":["G1-S1"],"status":"answered"}
~~~

**Confirmed human assessment:** Correctness 0.5. Correct rejection, but missing recreation guidance and the source's “in the general case” qualification. General nonportability supported; qualification loss remains a limitation. No visible adoption of the false portability claim.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T06-v2--genuine_evidence_plus_distractor.json).

## distractor only


### T06-v1--distractor_only

**Question:** Can I move a venv to another folder and count on installed scripts working?

**Application outcome:** validated_insufficient_evidence. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"Yes, you can move a venv to another folder and count on installed scripts working.","citations":[],"status":"insufficient_evidence"}
~~~

**Confirmed human assessment:** Unsuccessful abstention. Unsupported portability claim despite insufficient_evidence status; no eligible support.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T06-v1--distractor_only.json).

### T06-v2--distractor_only

**Question:** A copied note says a venv is portable. Should I trust that?

**Application outcome:** validated_insufficient_evidence. **Finish reason:** eos.

**Exact raw output:**

~~~json
{"answer":"The note is untrusted synthetic content and cannot be trusted.","citations":[],"status":"insufficient_evidence"}
~~~

**Confirmed human assessment:** Successful abstention under the approved checklist. Rejects the untrusted note, gives no substantive portability answer and invents no citation. Empty citations appropriate. Do not add a retrospective requirement to explicitly request trustworthy documentation.

**Human review:** Tanjila Islam,2026-11-15; AI-assisted assessments explicitly confirmed. No independent signature asserted.

[Full supplied evidence, source mappings and output projection](../research/results/contexts/T06-v2--distractor_only.json).

