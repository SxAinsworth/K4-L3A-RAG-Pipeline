# Research Report: Scholarship and University Student Services Corpus

**Researched:** 2026-09-20 (Asia/Ho_Chi_Minh)

## Scope and selection criteria

- Topic: university scholarships and related student support services in Vietnam.
- Minimum corpus: three public policy PDFs and five public articles/pages.
- Sources must be official university domains, retrievable without authentication, attributable by URL, and useful for grounded questions about eligibility, amounts, deadlines, or procedures.
- Excluded: pages containing student recipient lists, private data, third-party reposts, and sources requiring crawler bypass.

## Selected legal documents

| ID | Institution | Document | Public URL |
|---|---|---|---|
| `hust-scholarship-regulation-2018` | HUST | Scholarship regulation for students | https://hust.edu.vn/uploads/sys/sinh-vien/2019/03/20190301-dhbk-ha-noi-hoc-bong.375663.15135.pdf |
| `hust-phd-scholarship-regulation-2026` | HUST | PhD scholarship regulation | https://sdh.hust.edu.vn/Upload/19/Files/Quyche/2026/Quyet_dinh_hoc_bong_NCS.pdf |
| `hunre-scholarship-and-student-aid-regulation-2025` | HUNRE | 2025 scholarship and student-aid regulation | https://hunre.edu.vn/download/news/2025/07/04/142718_1872--%3Dpl__30062025103244_signed.pdf |

## Selected public articles/pages

| # | Institution | Topic | Public URL |
|---:|---|---|---|
| 1 | OU | Need-based scholarship | https://ou.edu.vn/hocbong/hbvk/ |
| 2 | OU | Back-to-school support scholarship | https://ou.edu.vn/hocbong/hbtsdtrg/ |
| 3 | OU | Academic merit scholarship | https://ou.edu.vn/hocbong/hbkhhtdhcq/ |
| 4 | OU | 2025–2026 need-based application procedure | https://ou.edu.vn/tin_tuc/thong-bao-ve-viec-tiep-nhan-ho-so-xet-cap-hoc-bong-vuot-kho-hoc-tap-hoc-ky-2-nam-hoc-2025-2026/ |
| 5 | OU | Scholarship application portal with current and historical notices | https://ou.edu.vn/hocbong/xet-tructuyen/ |

## Implementation recommendation

- Preserve the original binaries/JSON in `data/landing/`.
- Store URL, retrieval timestamp, title, checksum, and stable ID.
- Convert to Markdown under `data/standardized/legal/` and `data/standardized/news/` with YAML front matter.
- Re-running collection overwrites the same deterministic filenames rather than creating duplicates.
- Validate content manually after automated tests because minimum length and metadata checks do not prove semantic fidelity.

## Known limitations

- The corpus spans multiple universities and learner levels; retrieval queries should name the institution and audience when ambiguity matters.
- Article extraction is scoped to the page's article body, but output should still be reviewed before the final golden dataset.
- Policies can be superseded; `date_crawled`, source URL, and document version/year must remain visible in citations.
- The OU application portal includes both active and expired notices; downstream answers must check each notice's stated deadline rather than treating the whole page as current.
- An OU alumni scholarship-fund PDF and a Van Lang scholarship PDF were rejected because they are image-only; local rejected downloads are excluded from version control.
- A broad HCMUS student handbook was rejected because it included staff contact details outside the scholarship scope.
