# Platform scope — project owner decision

The current product version targets **Windows x64 and Linux x64 only**.

On **2026-10-27**, the project owner waived agent-run native validation for the
whole project: “i will test the work package(s) myself, on my own machine. no need
for you to do that.” Native build, install, runtime, security, replay and reference
performance testing are therefore **owner-run**. Missing native runners, exact
reference hardware, or power settings do not block agent delivery. Agents must
still implement package scope, run relevant available checks, and distinguish
cloud results from native evidence. The waiver does not certify untested behavior
or relax implementation, arithmetic, privacy, resource or transport invariants.

This decision supersedes older roadmap/package text that makes native machine
evidence a prerequisite for agent completion. Existing native test instructions
remain useful for the owner's testing.

The project owner explicitly deferred **all Mac support**, including Apple Silicon and Intel, to a later product version because **no one on the team owns a Mac and the team therefore cannot perform any Mac testing**.

Mac development, packaging, installers, signing/notarization, CI runners, testing and support are completely excluded from current work packages, milestones and release gates. Missing Mac hardware or validation cannot block this version. No future Mac delivery date is committed; reintroducing support requires an explicit future scope decision and access to Macs for testing.
