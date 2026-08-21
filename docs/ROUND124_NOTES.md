# Round 124 — persistent model-source endpoint configuration

The server could reach the Hugging Face mirror but not the canonical Hub. The
first mirror download was therefore started with a one-session environment
override, which was not sufficient for restart/recovery semantics.

The model asset boundary now accepts an explicit model-source environment
separate from model-service environment. The provider merges that environment
for the acquisition subprocess and still forces its managed `HF_HOME` cache.
The management configuration example documents the field. This keeps a mirror
or an enterprise endpoint in the platform configuration without putting it in
the model identity, changing the repository revision, or introducing a
second downloader.

The active server download remains on the fixed official Qwen repository
revision through the reachable mirror. The new configuration will be applied
to the next managed acquisition/recovery invocation after server regression.
