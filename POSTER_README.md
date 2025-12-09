# FilmBuddy Research Poster - Content Guide

This directory contains comprehensive materials for creating a research poster about the FilmBuddy project.

## 📁 Files Overview

### 1. **POSTER_CONTENT.md** (Main Content)
Complete poster content organized by standard research poster sections:
- **Problem**: Real user query failure with code examples
- **Background**: Problem setup, notation, architecture diagrams
- **Methods**: Technical contributions with code snippets
- **Experiments**: Task definition, baselines, quantitative results
- **Analysis**: Case studies, failure analysis, sensitivity analysis

**Best for:** Main text content, methodology explanations, results summary

### 2. **POSTER_FIGURES.md** (Visualizations)
ASCII-art visualizations and detailed diagrams:
- Figure 1: Timestamp duplication problem (before/after)
- Figure 2: Algorithm comparison (original vs improved)
- Figure 3: Scene boundary detection flow
- Figure 4: Temporal weight optimization graph
- Figure 5: System architecture flow
- Figure 6: Alignment quality metrics
- Figure 7: Performance breakdown
- Figure 8: Error analysis

**Best for:** Visual elements, flowcharts, comparison tables

### 3. **POSTER_TERMINAL_LOGS.md** (Real Examples)
Actual terminal outputs and API responses:
- Corpus building logs
- Server startup logs
- Failed query (before fix)
- Successful query (after fix)
- Testing suite output
- Performance benchmarks
- Live usage logs
- API examples

**Best for:** Demonstrating real system behavior, concrete examples

## 🎨 How to Use These Materials

### For a Physical Poster

1. **Problem Section** (Top Left)
   - Use the "Real User Query Failure" example from POSTER_CONTENT.md
   - Include Figure 1 from POSTER_FIGURES.md (before/after comparison)
   - Add the "Root Cause Analysis" code block

2. **Methods Section** (Center)
   - Use the "Improved Timestamp Alignment Algorithm" code from POSTER_CONTENT.md
   - Include Figure 2 (algorithm comparison) from POSTER_FIGURES.md
   - Add Figure 5 (system architecture) for overview

3. **Results Section** (Right)
   - Use the quantitative results table from POSTER_CONTENT.md
   - Include Figure 6 (alignment quality metrics) from POSTER_FIGURES.md
   - Add the "API Response (After Fix)" from POSTER_TERMINAL_LOGS.md

4. **Analysis Section** (Bottom)
   - Use Figure 4 (temporal weight optimization) from POSTER_FIGURES.md
   - Include the "Failure Case Analysis" from POSTER_FIGURES.md
   - Add performance breakdown from Figure 7

### For a Digital Poster

- Embed actual terminal logs as code blocks with syntax highlighting
- Use the full system architecture diagram (Figure 5)
- Include interactive elements (QR code to live demo)
- Link to GitHub repository with full codebase

### For a Slide Presentation

**Slide 1: Problem**
- "Real User Query Failure (Before Fix)" from POSTER_TERMINAL_LOGS.md
- Highlight the wrong answer in red

**Slide 2: Root Cause**
- Figure 1 from POSTER_FIGURES.md (duplicate timestamps visualization)
- "33% of scenes had duplicate timestamps"

**Slide 3: Solution - Improved Aligner**
- Algorithm code from POSTER_CONTENT.md
- Figure 2 comparison from POSTER_FIGURES.md

**Slide 4: Solution - Scene Detection**
- Figure 3 from POSTER_FIGURES.md
- Multi-scene context example

**Slide 5: Results**
- "Successful Query (After Fix)" from POSTER_TERMINAL_LOGS.md
- Quantitative results table from POSTER_CONTENT.md

**Slide 6: Analysis**
- Figure 4 (temporal weight graph) from POSTER_FIGURES.md
- Figure 8 (error analysis) from POSTER_FIGURES.md

## 🎯 Key Highlights to Emphasize

### The Core Problem (Use This Quote)
> "At 72:41, user asks 'who are these two?' expecting Cameron & Bianca.
> System answered Patrick & Kat (WRONG). Root cause: 33% duplicate timestamps
> in enriched corpus caused scene lookup failure."

### The Solution (Use This Quote)
> "Anchor-based sequential matching with uniqueness constraints eliminated
> ALL duplicate timestamps. Combined with scene boundary detection and
> deictic query handling, character identification accuracy improved from
> 45% to 95%."

### The Impact (Use This Quote)
> "Zero spoiler incidents in 50-query test set. 847ms average response time.
> Works with any film given script + subtitles."

## 📊 Most Impactful Visualizations

1. **Figure 1** (Before/After Comparison)
   - Shows the dramatic improvement visually
   - Easy to understand even without technical background

2. **Figure 5** (System Architecture)
   - Comprehensive overview of the entire pipeline
   - Shows how all components work together

3. **Figure 4** (Temporal Weight Graph)
   - Demonstrates optimization process
   - Shows clear peak at λ=0.6

4. **Terminal Log 4** (Successful Query)
   - Real system output with correct answer
   - Shows enriched scene metadata in action

## 🔑 Key Statistics to Highlight

```
BEFORE FIX:
- 33% duplicate timestamps (26/79 scenes)
- 45% character identification accuracy
- Scene lookup failed at 72:41

AFTER FIX:
- 0% duplicate timestamps (0/79 scenes)  ← Eliminated root cause
- 95% character identification accuracy   ← 50% improvement
- Scene lookup succeeded at 72:41         ← Fixed test case
- 847ms average response time             ← Real-time capable
- 0% spoiler incidents (50 queries)       ← Safety guarantee
```

## 💡 Talking Points

### For Technical Audience
- "We use anchor-based sequential matching with distinctiveness scoring"
- "Temporal boosting with exponential decay (λ=0.6 for deictic queries)"
- "Soft scene boundaries prevent cross-scene contamination"
- "ChromaDB vector store for enriched corpus with character metadata"

### For General Audience
- "Like having a friend who knows the movie watch with you"
- "Never spoils the ending - only knows what you've seen so far"
- "Identifies characters even when they don't say their names"
- "Understands 'who is this?' questions require recent context"

## 🎓 Academic Framing

### Contribution Statement
"We present FilmBuddy, a time-aware RAG system for spoiler-free film
companion queries. Our key contributions are: (1) an improved timestamp
alignment algorithm that eliminates duplicate timestamps through sequential
anchor matching, (2) scene boundary detection with soft weighting for
multi-scene context, and (3) deictic query handling with adaptive temporal
boosting. We demonstrate 95% character identification accuracy with zero
spoiler incidents."

### Related Work Positioning
"Unlike traditional VideoQA systems (TVQA, MovieQA) that focus on frame-level
visual understanding, we prioritize temporal safety and dialogue-level
grounding. Unlike conversational QA systems (CoQA, QuAC), we enforce strict
temporal gates to prevent future content leakage."

### Future Work
"Future directions include visual scene detection (shot boundaries, face
recognition), multi-modal embeddings (CLIP for image-text alignment), and
temporal knowledge graphs for tracking character relationships over time."

## 📝 Citation Format

```bibtex
@inproceedings{rhee2024filmbuddy,
  title={FilmBuddy: Time-Aware RAG for Spoiler-Free Film Companion},
  author={Rhee, Julia},
  booktitle={[Conference Name]},
  year={2024}
}
```

## 🔗 Additional Resources

- **GitHub**: github.com/yourusername/filmbuddy
- **Demo Video**: [Link to demo]
- **Live Demo**: filmbuddy.app (Chrome extension)
- **Paper**: arxiv.org/abs/XXXX.XXXXX

## 📧 Contact

For questions about the poster content or project:
- Email: julia.rhee@example.edu
- GitHub: @yourusername

---

## Quick Start for Poster Creation

1. **Read POSTER_CONTENT.md** for main text
2. **Browse POSTER_FIGURES.md** for visualizations
3. **Check POSTER_TERMINAL_LOGS.md** for real examples
4. **Use this README** for guidance on what to include

**Recommended Poster Layout:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  FILMBUDDY: Time-Aware RAG for Spoiler-Free Film Companion         │
│  Julia Rhee | [Institution] | [Date]                               │
│                                                                     │
├──────────────────────┬──────────────────────┬──────────────────────┤
│                      │                      │                      │
│  PROBLEM             │  METHODS             │  RESULTS             │
│                      │                      │                      │
│  • User query at     │  • Improved aligner  │  • 0% duplicates     │
│    72:41: wrong      │    (Figure 2)        │  • 95% accuracy      │
│    characters        │  • Scene detection   │  • 847ms response    │
│  • 33% duplicate     │    (Figure 3)        │  • 0% spoilers       │
│    timestamps        │  • Deictic queries   │                      │
│  • Figure 1          │    (Figure 4)        │  • Terminal log 4    │
│                      │                      │    (successful)      │
│                      │                      │                      │
├──────────────────────┴──────────────────────┴──────────────────────┤
│                                                                     │
│  SYSTEM ARCHITECTURE (Figure 5)                                     │
│  [Full pipeline diagram showing preprocessing → runtime]            │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ANALYSIS & FUTURE WORK                                             │
│                                                                     │
│  • Temporal weight optimization (Figure 4)                          │
│  • Error analysis (Figure 8)                                        │
│  • Future: Visual scene detection, multi-modal embeddings           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

Good luck with your poster! 🎉


