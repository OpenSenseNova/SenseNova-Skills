# SenseNova Skills Biweekly Report

👋 Welcome to SenseNova Skills, an open-source library purpose-built for office automation and workplace efficiency. It currently covers core scenarios including data visualization(Infographics), presentation generation, Excel data analysis, and multi-source deep research. Designed with high compatibility, the project seamlessly integrates into major Agent frameworks, aiming to unlock the true productivity value of AI in office environments through engineered skill extensions.

⏰ The SenseNova Skills Bi-weekly regularly recaps the latest project iterations and community updates, keeping developers and users fully up-to-speed with our technical roadmap.

> 💡 Note: Bi-weekly updates are listed in reverse chronological order.
---

## 2026.7.27 - 8.9

### Deep Research

Actively in development 🧑‍💻👩‍💻

### PPT

#### PPT Skill v2: Rebuilt Unified Generation Pipeline

Over the past two weeks we shipped a milestone release of PPT Skill v2. Rather than bolting another mode onto the existing flow, we rebuilt the pipeline end to end — from understanding the request and parsing materials, through research and narrative structuring, to page generation and delivery — and got both core routes, Static HTML and Dynamic HTML, working end to end. It's now open for anyone to use: 

- **Unified entry point**: Every request enters through `sn-ppt-entry` and flows through `material understanding → optional research (targeted search for Standard, full Deep Research for Deep) → a shared Story (outline.md, readable and editable) → Static or Dynamic HTML generation`. Depth, output format, and design richness are three independent choices — the system can recommend defaults, or you can override any of them. 
- **Static HTML**: Keeps the effect baseline we've tuned across a large set of samples — per-page generation with visual self-checks and full review passes — and now ships both a full-fidelity HTML deck and a PPTX-compatible export by default. The HTML-to-PPTX converter got stronger at handling tables, charts, and complex backgrounds; a failed conversion never affects the HTML deck that's already generated. 
- **Dynamic HTML**: Now handled by `sn-ppt-dazzle`, building on the shared Story to produce a single-file presentation with navigation, transitions, animated backgrounds, and interactive effects — still backed by `CSS, SVG, Canvas, ECharts, Shader, and Three.js`.
- **Task handling and tooling**: Task artifacts now land in a fixed, predictable directory, and interrupted runs resume from where they left off instead of starting over. Search and image generation prefer the native tools of the Agent you're running, falling back to the bundled tools only when those aren't available. 
- **Workbench**: Added full editing support for Dynamic HTML decks, plus fixes for a batch of rough edges — drag-and-drop editing, in-place text editing, and page-flip flicker. The progress page now reflects real task state instead of marking partial completion as done. 
Going forward, we'll keep collecting real-world generations to sharpen visual quality, long-task feedback, Dynamic HTML compatibility, and HTML-to-PPTX fidelity, and to fully connect Workbench with the new generation pipeline.

### Image Generation

Actively in development 🧑‍💻👩‍💻

---

## 2026.7.6 - 7.26

### Deep Research

#### Real-Time Task-Flow Tracking on the Web

Task progress can now be tracked live in the browser across both Normal and Heavy modes, with every execution stage and intermediate artifact surfaced end to end.

#### Rebuilt Task Execution Pipeline

The pipeline is now more flexible: previously fetched material can be reused (all cached under source_cache/), and the report's output format can be chosen dynamically to fit the task at hand.

#### Multilingual Consistency Fix

Skill invocation logic has been refined so that the working language stays aligned with the user's system settings or input language, eliminating mixed-language output.

### PPT

#### PPT Workbench

The new Workbench delivers a one-stop, closed loop from generation to editing:

- **Live generation and preview**: A new task-progress page lets you view slides and JSON artifacts as they are generated. It intelligently follows the latest progress by default and, once finished, transitions seamlessly into the editor.
- **Precise visual editing**: An upgraded three-pane layout supports free drag-and-drop and modification of elements, and lets you select a specific on-slide element to submit to the AI for targeted revision, preventing accidental edits to the rest of the page.
- **Presenting, exporting, and troubleshooting**: Supports full-screen immersive playback and PPTX / PDF / image export, with a built-in file panel for directly diagnosing missing images or path errors.
- **Experience and performance optimizations**: Fixed rendering-size and image-display anomalies, provided a prebuilt Runtime (ready out of the box, no dependency configuration required), and optimized the portrait-mode layout and input-box experience.

### Image Generation

#### [Issue #109](https://github.com/OpenSenseNova/SenseNova-Skills/issues/109) fixed: Enhanced Error Messaging for Image-Generation Failures

For Gemini / Nano Banana image-generation failures, precise error-cause messages were added to speed up troubleshooting.

---

## 2026.6.22 - 7.5

### Deep Research 

**Now supports three modes: `quick/normal/heavy`**

Deep Research now supports three modes — `quick/normal/heavy`. You can specify a mode explicitly, or let the model recommend one based on the complexity of the question, the evidence required, and the goal of the report. The three modes differ as follows:

| **Mode** | **Estimated time**  | **Best for**                                                                                                                              | **Output characteristics**                                                                                                                                                            | **Examples**                                                                                                                                                  |
|----------|---------------------|-------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| quick    | ~10 minutes         | Simple fact-checking, single questions, single-dimension lookups                                                                          | Delivers a reliable answer quickly; typically relies on a few authoritative sources without full multi-source cross-validation                                                        | When does a certain policy take effect? Who is the current CEO of a given company?                                                                            |
| normal   | ~30 minutes         | Industry overviews, competitor comparisons, policy interpretation, trend analysis, and other questions that need fairly complete coverage | Breaks the topic into multiple research dimensions, performs multi-source evidence gathering, verification, and structured writing to produce a report with fairly complete coverage  | Analyze the current state of the home-robotics supply chain; compare the capabilities and positioning of three AI office products                             |
| heavy    | ~60 minutes or more | Highly complex, high-stakes, or deep-dive questions such as strategic research, investment due diligence, and complex causal analysis     | Builds on normal with additional rounds of research, multi-perspective review, targeted follow-up research, and section-by-section writing to produce a more in-depth research report | Assess whether now is the right time to enter the embodied-intelligence space; conduct full market and competitive due diligence for a new business direction |

> 👀 TIPS:
> - If you are unsure which mode to choose, simply describe your research goal and let the model recommend one;
> - Choose quick when you are short on time or only need to verify a single fact, normal when you need a complete report, and heavy when you need in-depth due diligence or strategic judgment.

### PPT

We are rolling out a more comprehensive update to PPT generation. Stay tuned.

### Image Generation

Related features are currently being updated.



## 2026.6.8 – 6.21 

### Deep Research

**1. Deep Research**
We have rebuilt Deep Research. It now runs each investigation through a complete five-step flow: understand the request → draft a research plan → gather evidence across multiple dimensions → synthesize → generate the report. Intermediate results from every step are saved along the way, so an interrupted run can resume instead of starting over.

For evidence gathering, we connected more specialized data sources for each dimension. This release adds three new source types to make results more authentic and reliable:

- China market: covers the Chinese market, macroeconomics, regulatory policy, public tenders, and listed-company disclosures
- Annual reports: covers corporate annual and periodic reports
- Social media: covers public trending topics, encyclopedia trends, and the developer ecosystem

We also significantly expanded academic search, integrating sources such as arXiv, Crossref, OpenAlex, Google Scholar, and Semantic Scholar, with support for following citation chains.

The system retains the evidence and sources behind each investigation and cross-checks them, producing results that can be traced and verified. This keeps user-facing reports comprehensive and well-grounded, reduces AI hallucination, and makes them ready for real-world use.

> Note: explicit citation numbering in the report body is still being refined; in the current version, source information is mainly preserved within the research results.

**2. Other Functions Update**
- Full-version research is now live: reports are more comprehensive, with traceable sources for cited content. A faster quick mode will follow to shorten generation time.
- Upgraded HTML report rendering: For data analysis and deep research, the HTML styling has been upgraded for better visualization.

Going forward, we will keep optimizing Deep Research generation speed to further improve the experience.

### PPT
- Fast Mode Demo: Launched Fast Mode: users can choose between a quick preview of partial results or full generation. After generating a PPT in fast mode, the system also offers revision suggestions to help produce content faster and more accurately.
- Combined standard mode with infographics: when a generated page involves flowcharts or infographics, the system calls the SenseNova U1 model to generate the image, yielding better results than the previous SVG-assembled infographics.

We will add more templates and reference cases to further improve generation quality.

