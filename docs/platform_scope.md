# Platform scope — project owner decision

The current product version targets **Windows x64 and Linux x64 only**. Build, install, runtime, security and numerical/replay acceptance require native evidence on those two targets.

The project owner explicitly deferred **all Mac support**, including Apple Silicon and Intel, to a later product version because **no one on the team owns a Mac and the team therefore cannot perform any Mac testing**.

Mac development, packaging, installers, signing/notarization, CI runners, testing and support are completely excluded from current work packages, milestones and release gates. Missing Mac hardware or validation cannot block this version. No future Mac delivery date is committed; reintroducing support requires an explicit future scope decision and access to Macs for testing.
