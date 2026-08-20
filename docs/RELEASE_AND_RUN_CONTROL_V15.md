# Release / Run Control — Round 15

## Hash-complete release identity

Every source/config/doc file in a release is listed with size + SHA-256. The release manifest has a tree digest. The deterministic ZIP normalizes entry order, timestamp and permissions, so building the same tree twice produces the same package bytes.

## Launch identity

`RunLaunchManifest` binds the parts that must not drift across a confirmatory run or exact recovery:

- release digest;
- prompt generation digest;
- role→model deployment manifest digest;
- Method ID/version/ABI;
- Environment ID/version/ABI;
- Study spec digest;
- target host fingerprint;
- exact launch argv;
- config file digests;
- seed identity.

No secret values are required in the launch manifest.

## Exact server startup plan

Startup is ordered as read-only identity verification → target inventory → qualified model service activation → READY → exact role canaries → Method/Environment ABI verification → Study start. Failure stops at the owning step; no fallback model or reduced configuration is selected.
