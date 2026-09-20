# Benchmark cout / energie - 1M tokens generes par modele

Prompt utilise pour tous les modeles : `écris moi l'histoire la plus longue possible`

Methodologie : warm-up puis generation reelle, `num_ctx=8192` force pour TOUS les modeles (comparaison equitable, evite le bug d'OOM au chargement quand un modele part sur son contexte max par defaut - voir `benchmark_1M_tokens_unbounded_context.md` pour le run precedent sans cette limite). Puissance GPU moyenne mesuree pendant l'appel (NVML, RTX 5060 Ti), extrapolee a 1M tokens generes. Cout = electricite seule (hors amortissement materiel). 1 seul run par modele.

| Modele | Tokens generes | Vitesse (tok/s) | Puissance moy. (W) | Energie / 1M tokens (kWh) | Cout / 1M tokens (France, $) | Equiv. rameur | Notes |
|---|---|---|---|---|---|---|---|
| gemma3:1b | 2377 | 261.8 | 88.3 | 0.0937 | 0.0273 | 9 min | 9488 caracteres generes |
| granite3.1-dense:2b | 1791 | 185.7 | 122.7 | 0.1836 | 0.0536 | 18 min | 6885 caracteres generes |
| qwen2.5:3b | 1377 | 160.4 | 121.4 | 0.2103 | 0.0613 | 21 min | 5001 caracteres generes |
| qwen3:4b | 8582 | 104.9 | 163.7 | 0.4337 | 0.1265 | 43 min | 7814 caracteres generes |
| gemma3:4b | 2307 | 116.4 | 133.6 | 0.3188 | 0.0930 | 32 min | 8845 caracteres generes |
| llama3.1:8b | 1946 | 76.5 | 152.9 | 0.5548 | 0.1618 | 55 min | 6847 caracteres generes |
| granite3.1-dense:8b | 951 | 71.1 | 133.2 | 0.5205 | 0.1518 | 52 min | 2853 caracteres generes |
| minicpm-v:latest | 479 | 88.2 | 91.8 | 0.2890 | 0.0843 | 29 min | 1839 caracteres generes |
| qwen3.5:9b | 5948 | 65.8 | 157.7 | 0.6656 | 0.1941 | 1.1 h | 17504 caracteres generes |
| gemma4:latest | 2874 | 95.0 | 138.4 | 0.4044 | 0.1179 | 40 min | 8686 caracteres generes |
| deepseek-r1:8b | 6528 | 67.7 | 161.0 | 0.6604 | 0.1926 | 1.1 h | 21120 caracteres generes |
| phi4:14b | 1193 | 26.9 | 107.5 | 1.1111 | 0.3241 | 1.8 h | 4362 caracteres generes |
| qwen3:30b-a3b | 5430 | 53.3 | 72.1 | 0.3758 | 0.1096 | 37 min | 6697 caracteres generes |
| smollm2:135m | 81920 | 519.6 | 125.5 | 0.0671 | 0.0196 | 7 min | 211643 caracteres generes |
| qwen2.5:0.5b | 111 | 481.3 | 26.6 | 0.0153 | 0.0045 | 2 min | ⚠️ PEU D'ECHANTILLONS: histoire tres courte a 2 essais consecutifs -> puissance moyenne dominee par la rampe de demarrage GPU, a prendre avec prudence |
| mistral-nemo:12b | 977 | 54.5 | 126.6 | 0.6447 | 0.1880 | 1.1 h | 4445 caracteres generes |
| qwen2.5vl:7b | 151 | 78.4 | 30.9 | 0.1093 | 0.0319 | 11 min | ⚠️ PEU D'ECHANTILLONS + DETERMINISTE (temperature=0.0001 dans son Modelfile): produit exactement la meme reponse courte a chaque essai, un retest ne peut pas aider |

## A prendre avec prudence

- **smollm2:135m et mistral-nemo:12b : resolus au 2e essai.** Le 1er essai
  avait produit une histoire trop courte (mesure fragile, peu
  d'echantillons). Un 2eme essai avec le meme prompt/parametres a suffi -
  simple variabilite d'echantillonnage (temperature > 0), pas un probleme
  structurel. Les valeurs du tableau ci-dessus sont celles du 2e essai
  (fiable : 40 a 319 echantillons de puissance).
- **qwen2.5:0.5b : reste une mesure fragile apres 2 essais.** Histoire tres
  courte les deux fois (99 puis 111 tokens, ~0.2s, 5 echantillons de
  puissance a chaque fois) - semble etre un vrai comportement du modele
  (s'arrete vite) plutot qu'un coup de malheur ponctuel, mais la puissance
  moyenne mesuree reste dominee par la rampe de demarrage GPU. A prendre
  avec prudence.
- **qwen2.5vl:7b : reessai inutile, modele deterministe.** Son Modelfile
  fixe `temperature=0.0001` - il produit litteralement la meme reponse de
  151 tokens a chaque appel avec le meme prompt. Relancer avec le meme
  prompt ne peut donc jamais ameliorer la mesure (8 echantillons de
  puissance, moyenne peu fiable) ; il faudrait changer le prompt pour
  obtenir une reponse plus longue, ce qui casserait la comparabilite avec
  les autres modeles - laisse tel quel.

## Observations

- **MoE vs dense : le total de parametres ne dit pas tout.** `qwen3:30b-a3b`
  (30B de parametres au total, ~3B actifs par token) tourne a seulement
  ~72 W de moyenne - moins que la plupart des modeles denses 7-9B testes
  (llama3.1:8b 153 W, qwen3.5:9b 158 W, deepseek-r1:8b 161 W) et proche de
  modeles denses bien plus petits. Ca confirme l'hypothese de depart : le
  cout d'un MoE suit son nombre de parametres *actifs*, pas son poids total
  sur le disque. Sur ce GPU, qwen3:30b-a3b finit moins cher au 1M tokens
  (0,110 $) que des modeles denses 4 a 5 fois plus petits en parametres
  totaux (llama3.1:8b 0,162 $, qwen3.5:9b 0,194 $).

## Cout par pays (USD / 1M tokens generes)

| Modele | France | USA | China | DR Congo | Brazil |
|---|---|---|---|---|---|
| gemma3:1b | 0.0273 | 0.0157 | 0.0084 | 0.0067 | 0.0150 |
| granite3.1-dense:2b | 0.0536 | 0.0307 | 0.0164 | 0.0130 | 0.0295 |
| qwen2.5:3b | 0.0613 | 0.0352 | 0.0188 | 0.0149 | 0.0337 |
| qwen3:4b | 0.1265 | 0.0725 | 0.0388 | 0.0308 | 0.0696 |
| gemma3:4b | 0.0930 | 0.0533 | 0.0285 | 0.0226 | 0.0512 |
| llama3.1:8b | 0.1618 | 0.0928 | 0.0496 | 0.0394 | 0.0890 |
| granite3.1-dense:8b | 0.1518 | 0.0870 | 0.0466 | 0.0370 | 0.0835 |
| minicpm-v:latest | 0.0843 | 0.0483 | 0.0258 | 0.0205 | 0.0464 |
| qwen3.5:9b | 0.1941 | 0.1113 | 0.0595 | 0.0473 | 0.1068 |
| gemma4:latest | 0.1179 | 0.0676 | 0.0362 | 0.0287 | 0.0649 |
| deepseek-r1:8b | 0.1926 | 0.1104 | 0.0591 | 0.0469 | 0.1060 |
| phi4:14b | 0.3241 | 0.1858 | 0.0994 | 0.0789 | 0.1783 |
| qwen3:30b-a3b | 0.1096 | 0.0628 | 0.0336 | 0.0267 | 0.0603 |
| smollm2:135m | 0.0196 | 0.0112 | 0.0060 | 0.0048 | 0.0108 |
| qwen2.5:0.5b | 0.0045 | 0.0026 | 0.0014 | 0.0011 | 0.0025 |
| mistral-nemo:12b | 0.1880 | 0.1078 | 0.0577 | 0.0458 | 0.1034 |
| qwen2.5vl:7b | 0.0319 | 0.0183 | 0.0098 | 0.0078 | 0.0175 |
