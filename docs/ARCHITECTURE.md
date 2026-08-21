# Project Tesseract & ISSI Compression Architecture

## 1. Overview
This project unifies the research, algorithmic specifications, 3D interactive visualizations, and tensor streaming offloading engine developed during the **ISSI Compression Rework** and **Project Tesseract** sessions.

---

## 2. Core Subsystems

### A. ISSI (Integer String Substitution Index) Compression
* **Lexical Optimization**: Strips redundant grammatical stop-words and prepositions while preserving high-entropy semantic tokens.
* **Static & Dynamic n-gram Tokenization**: Maps recurring multi-word phrases and common user prompt signatures to ultra-compact tokens (e.g. `{H1}`, `[D1]`).
* **Cross-Session Memory & Tagging**: Retains conversational context across topic veers using synthetic synapse metadata ("synthurons" and "hyper hubs").

### B. 48-Character 3-Tier Deterministic Scoring
* Characters ($A-Z, 0-9, \text{special code tokens}$) are assigned deterministic scores across 3 equal 16-element tiers (**LOWER**, **MIDDLE**, **UPPER**).
* Average token score controls:
  * **Ingress Direction**: Clockwise (CW) for Lower vs Counter-Clockwise (CCW) for Upper.
  * **Plane Permutation**: $X \to Y \to Z$ vs $Z \to Y \to X$ for Middle tier.

### C. 3D Center-Out Spiral Tesseract Winding
* **Adaptive Dynamic Sizing**: Calculates the smallest enclosing cube among $5^3, 7^3, 9^3, 10^3, 12^3, 14^3, 16^3, 18^3, 20^3$.
* **Center-Out Radiating Ingress**: Winding begins at the exact dead-center voxel $(\lfloor \frac{D}{2} \rfloor, \lfloor \frac{D}{2} \rfloor, \lfloor \frac{D}{2} \rfloor)$ and spirals outward across 3D planes simultaneously, leaving the encoded designator tail at the perimeter.

### D. 4-Corner Top-Down Orthogonal Unwinding Scan
* Cube voxels are read top-to-bottom rotating through the 4 corners:
  * **Plane 0 (Top)**: Top-Rear-Left $\to$ Left-to-Right sweep
  * **Plane 1 (Next)**: Top-Rear-Right $\to$ Right-to-Left sweep
  * **Plane 2 (Next)**: Bottom-Front-Right $\to$ Front-to-Back sweep
  * **Plane 3 (Next)**: Bottom-Front-Left $\to$ Back-to-Front sweep
  * **Plane 4+**: Cycles modulo 4 through the base plane.

### E. 5+1 Homophonic Substitution Obfuscation
* Maps characters across 6 historical scripts:
  1. **Classical / Archaic Latin**
  2. **Ancient Greek**
  3. **Sanskrit / Brahmi**
  4. **Egyptian Hieroglyphs**
  5. **Sumerian Cuneiform**
  6. **Elder Futhark Nordic Runes**
* Reversible and frequency-analysis resistant.

### F. Layer-Streaming Engine & Dynamic Tensor Router (PyTorch)
* Memory-mapped zero-copy parameter access via `safetensors`.
* Double-buffered asynchronous PCIe DMA transfers using CUDA streams.
* Hysteresis VRAM buffer manager with high/low watermark caching.
