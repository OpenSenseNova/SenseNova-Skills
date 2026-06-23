# SenseNova Skills Biweekly Report

👋 Welcome to SenseNova Skills, an open-source library purpose-built for office automation and workplace efficiency. It currently covers core scenarios including data visualization(Infographics), presentation generation, Excel data analysis, and multi-source deep research. Designed with high compatibility, the project seamlessly integrates into major Agent frameworks, aiming to unlock the true productivity value of AI in office environments through engineered skill extensions.

⏰ The SenseNova Skills Bi-weekly regularly recaps the latest project iterations and community updates, keeping developers and users fully up-to-speed with our technical roadmap.

> 💡 Note: Bi-weekly updates are listed in reverse chronological order.

## 2026.06.08 – 06.21 

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

