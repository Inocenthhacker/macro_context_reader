# Citing & Academic Attribution

This project builds on academic models, datasets, and methodologies developed by other researchers. If you use this code or its outputs, please cite the relevant works below according to the components you used.

## Pre-trained Models

### FOMC-RoBERTa (primary NLP model for FOMC scoring)

> Shah, A., Paturi, S., & Chava, S. (2023). Trillion Dollar Words: A New Financial Dataset, Task & Market Analysis. *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (ACL 2023)*, 6664–6679. https://aclanthology.org/2023.acl-long.368/

```bibtex
@inproceedings{shah2023trillion,
  title={Trillion Dollar Words: A New Financial Dataset, Task \& Market Analysis},
  author={Shah, Agam and Paturi, Suvan and Chava, Sudheer},
  booktitle={Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)},
  pages={6664--6679},
  year={2023},
  publisher={Association for Computational Linguistics},
  url={https://aclanthology.org/2023.acl-long.368/}
}
```

**License:** CC BY-NC 4.0 (non-commercial only)
**Used in:** `src/macro_context_reader/rhetoric/scorers/fomc_roberta.py`

### FinBERT-FOMC (kept as backup model)

> Chen, Z., Wang, Y., & Yang, Y. (2023). FinBERT-FOMC: A Sentiment Analysis Model for FOMC Statements. *Proceedings of the 4th ACM International Conference on AI in Finance (ICAIF 2023)*. https://doi.org/10.1145/3604237.3626843

```bibtex
@inproceedings{chen2023finbert,
  title={FinBERT-FOMC: A Sentiment Analysis Model for FOMC Statements},
  author={Chen, Ziwei and Wang, Yiqing and Yang, Yi},
  booktitle={Proceedings of the 4th ACM International Conference on AI in Finance},
  year={2023},
  doi={10.1145/3604237.3626843}
}
```

**Used in:** `src/macro_context_reader/rhetoric/scorers/finbert_fomc.py` (deprecated 2026-04-12 due to 20% empirical accuracy, kept as backup)

### FinBERT (base model)

> Huang, A. H., Wang, H., & Yang, Y. (2023). FinBERT: A Large Language Model for Extracting Information from Financial Text. *Contemporary Accounting Research*, 40(2), 806–841. https://doi.org/10.1111/1911-3846.12832

```bibtex
@article{huang2023finbert,
  title={FinBERT: A Large Language Model for Extracting Information from Financial Text},
  author={Huang, Allen H. and Wang, Hui and Yang, Yi},
  journal={Contemporary Accounting Research},
  volume={40},
  number={2},
  pages={806--841},
  year={2023},
  doi={10.1111/1911-3846.12832}
}
```

**Used indirectly** via Cleveland Fed Beige Book Sentiment Indices (pre-computed FinBERT scores).

### Sentence-BERT (all-MiniLM-L6-v2)

> Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. *Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing*. https://arxiv.org/abs/1908.10084

```bibtex
@inproceedings{reimers2019sentence,
  title={Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks},
  author={Reimers, Nils and Gurevych, Iryna},
  booktitle={Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing},
  year={2019},
  url={https://arxiv.org/abs/1908.10084}
}
```

**License:** Apache 2.0
**Used in:** `src/macro_context_reader/rhetoric/matched_filter.py`

### Llama 3.3 70B (Meta AI)

> Meta AI (2024). Llama 3.3 70B Instruct. https://ai.meta.com/llama/

Accessed via DeepInfra API.
**Used in:** `src/macro_context_reader/rhetoric/scorers/llama_deepinfra.py`

## Datasets

### Cleveland Fed Beige Book Sentiment Indices

> Filippou, I., Garciga, C., Mitchell, J., & Nguyen, M. T. (2024). Regional Economic Sentiment: Constructing Quantitative Estimates from the Beige Book and Testing Their Ability to Forecast Recessions. *Federal Reserve Bank of Cleveland, Economic Commentary 2024-08*. https://doi.org/10.26509/frbc-ec-202408

```bibtex
@techreport{filippou2024regional,
  title={Regional Economic Sentiment: Constructing Quantitative Estimates from the Beige Book and Testing Their Ability to Forecast Recessions},
  author={Filippou, Ilias and Garciga, Christian and Mitchell, James and Nguyen, My T.},
  year={2024},
  institution={Federal Reserve Bank of Cleveland},
  type={Economic Commentary},
  number={2024-08},
  doi={10.26509/frbc-ec-202408}
}
```

**Data source:** https://www.openicpsr.org/openicpsr/project/205881/
**License:** CC BY-NC 4.0
**Used in:** `src/macro_context_reader/economic_sentiment/`

## Methodologies

### Expected Rate Change Formula (Gürkaynak-Sack-Swanson 2005)

> Gürkaynak, R. S., Sack, B., & Swanson, E. (2005). Do Actions Speak Louder Than Words? The Response of Asset Prices to Monetary Policy Actions and Statements. *International Journal of Central Banking*, 1(1), 55–93.

```bibtex
@article{gurkaynak2005actions,
  title={Do Actions Speak Louder Than Words? The Response of Asset Prices to Monetary Policy Actions and Statements},
  author={G{\"u}rkaynak, Refet S. and Sack, Brian and Swanson, Eric},
  journal={International Journal of Central Banking},
  volume={1},
  number={1},
  pages={55--93},
  year={2005}
}
```

**Used in:** `src/macro_context_reader/market_pricing/fedwatch/surprise.py` (method `expected_change`)

### Kullback-Leibler Divergence

> Kullback, S., & Leibler, R. A. (1951). On Information and Sufficiency. *Annals of Mathematical Statistics*, 22(1), 79–86.

```bibtex
@article{kullback1951information,
  title={On Information and Sufficiency},
  author={Kullback, Solomon and Leibler, Richard A.},
  journal={Annals of Mathematical Statistics},
  volume={22},
  number={1},
  pages={79--86},
  year={1951}
}
```

**Used in:** `src/macro_context_reader/market_pricing/fedwatch/surprise.py` (method `kl_divergence`)

### Matched-Filter Weighting for FOMC Speeches (Djourelova et al. 2025)

> Djourelova, M., et al. (2025). Reference for matched-filter cosine similarity weighting of Fed officials' speeches relative to FOMC press conferences. [Working paper, Chicago Fed]

**Used in:** `src/macro_context_reader/rhetoric/matched_filter.py`

### Early Warning Signals (Scheffer et al. 2009)

> Scheffer, M., Bascompte, J., Brock, W. A., Brovkin, V., Carpenter, S. R., Dakos, V., Held, H., van Nes, E. H., Rietkerk, M., & Sugihara, G. (2009). Early-warning signals for critical transitions. *Nature*, 461(7260), 53–59. https://doi.org/10.1038/nature08227

```bibtex
@article{scheffer2009early,
  title={Early-warning signals for critical transitions},
  author={Scheffer, Marten and Bascompte, Jordi and Brock, William A. and Brovkin, Victor and Carpenter, Stephen R. and Dakos, Vasilis and Held, Hermann and van Nes, Egbert H. and Rietkerk, Max and Sugihara, George},
  journal={Nature},
  volume={461},
  number={7260},
  pages={53--59},
  year={2009},
  doi={10.1038/nature08227}
}
```

**Planned use in:** `src/macro_context_reader/monitoring/` (EWS panel, PRD-051)

### Dempster-Shafer Evidence Theory

> Dempster, A. P. (1967). Upper and Lower Probabilities Induced by a Multivalued Mapping. *Annals of Mathematical Statistics*, 38(2), 325–339.

> Shafer, G. (1976). *A Mathematical Theory of Evidence*. Princeton University Press.

```bibtex
@article{dempster1967upper,
  title={Upper and Lower Probabilities Induced by a Multivalued Mapping},
  author={Dempster, Arthur P.},
  journal={Annals of Mathematical Statistics},
  volume={38},
  number={2},
  pages={325--339},
  year={1967}
}

@book{shafer1976mathematical,
  title={A Mathematical Theory of Evidence},
  author={Shafer, Glenn},
  year={1976},
  publisher={Princeton University Press}
}
```

**Planned use in:** `src/macro_context_reader/output/` (PRD-500 DST fusion)

### PCR5 Combination Rule (Dezert-Smarandache 2004)

> Dezert, J., & Smarandache, F. (2004). Proportional Conflict Redistribution Rules for Information Fusion. In *Advances and Applications of DSmT for Information Fusion* (Vol. 2).

```bibtex
@incollection{dezert2004pcr5,
  title={Proportional Conflict Redistribution Rules for Information Fusion},
  author={Dezert, Jean and Smarandache, Florentin},
  booktitle={Advances and Applications of DSmT for Information Fusion},
  volume={2},
  year={2004}
}
```

**Planned use in:** `src/macro_context_reader/output/combination_rules/pcr5.py`

## Data Sources (Acknowledgments)

This project consumes public data from the following institutions (no academic citation required, but acknowledgment is appreciated):

- **Federal Reserve (FRED API)** — https://fred.stlouisfed.org/
- **Federal Reserve Board (FOMC documents)** — https://federalreserve.gov/
- **European Central Bank (ECB Data Portal)** — https://data.ecb.europa.eu/
- **CME Group (FedWatch tool)** — https://www.cmegroup.com/
- **CFTC (Commitment of Traders)** — https://www.cftc.gov/

## Citing this project

If you use this codebase in your research, please cite the underlying models/datasets above (relevant to your usage). For citing the project structure itself, see `CITATION.cff`.

## License compliance

- **FOMC-RoBERTa, Cleveland Fed indices:** CC BY-NC 4.0 — non-commercial use only
- **FinBERT-FOMC:** check individual model card on Hugging Face
- **Sentence-BERT all-MiniLM-L6-v2:** Apache 2.0
- **This project:** non-commercial personal use (per pyproject.toml)
