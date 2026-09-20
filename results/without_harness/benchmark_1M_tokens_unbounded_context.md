# Benchmark cout / energie - 1M tokens generes par modele

Prompt utilise pour tous les modeles : `écris moi l'histoire la plus longue possible`

Methodologie : warm-up puis generation reelle (sans limite de longueur), puissance GPU moyenne mesuree pendant l'appel (NVML, RTX 5060 Ti), extrapolee a 1M tokens generes. Cout = electricite seule (hors amortissement materiel). 1 seul run par modele.

| Modele | Tokens generes | Vitesse (tok/s) | Puissance moy. (W) | Energie / 1M tokens (kWh) | Cout / 1M tokens (France, $) | Equiv. rameur | Notes |
|---|---|---|---|---|---|---|---|
| gemma3:1b | 1399 | 264.4 | 67.9 | 0.0713 | 0.0208 | 7 min | 5340 caracteres generes |
| granite3.1-dense:2b | 1981 | 29.4 | 22.5 | 0.2121 | 0.0619 | 21 min | 7234 caracteres generes |
| qwen2.5:3b | 703 | 165.4 | 85.2 | 0.1432 | 0.0418 | 14 min | 2599 caracteres generes |
| qwen3:4b | - | - | - | - | - | - | ERREUR: 500 Server Error: Internal Server Error for url: http://localhost:11435/api/generate |
| gemma3:4b | 2313 | 81.8 | 86.2 | 0.2929 | 0.0854 | 29 min | 9439 caracteres generes |
| llama3.1:8b | 1100 | 11.2 | 13.8 | 0.3419 | 0.0997 | 34 min | ⚠️ SUSPECT: puissance GPU quasi au repos (13.8W) + vitesse tres faible pour un 8B -> probable repli partiel sur CPU, chiffres non comparables aux autres |
| granite3.1-dense:8b | - | - | - | - | - | - | ERREUR: 500 Server Error: Internal Server Error for url: http://localhost:11435/api/generate |
| minicpm-v:latest | 807 | 84.9 | 107.1 | 0.3502 | 0.1021 | 35 min | 3103 caracteres generes |
| qwen2.5vl:7b | 190 | 14.6 | 24.4 | 0.4649 | 0.1356 | 46 min | ⚠️ SUSPECT: puissance GPU quasi au repos (24.4W) + vitesse tres faible pour un 7B -> probable repli partiel sur CPU, chiffres non comparables aux autres |
| qwen3.5:9b | 8081 | 45.4 | 113.9 | 0.6970 | 0.2033 | 1.2 h | 26362 caracteres generes |
| gemma4:latest | 2724 | 96.0 | 137.0 | 0.3964 | 0.1156 | 39 min | 7996 caracteres generes |
| smollm2:135m | 81920 | 311.4 | 56.8 | 0.0506 | 0.0148 | 5 min | 191947 caracteres generes |
| qwen2.5:0.5b | 80 | 372.0 | 37.4 | 0.0279 | 0.0081 | 3 min | ⚠️ PEU FIABLE: generation arretee apres seulement 80 tokens / 0.2s (5 echantillons de puissance seulement) -> moyenne dominee par la rampe de demarrage, pas un vrai regime etabli |
| mistral-nemo:12b | - | - | - | - | - | - | ERREUR: 500 Server Error: Internal Server Error for url: http://localhost:11435/api/generate |
| deepseek-r1:8b | - | - | - | - | - | - | ERREUR: 500 Server Error: Internal Server Error for url: http://localhost:11435/api/generate |
| phi4:14b | 1159 | 9.1 | 34.2 | 1.0399 | 0.3033 | 1.7 h | ⚠️ SUSPECT: puissance GPU quasi au repos (34.2W) + vitesse tres faible pour un 14B (9.1 tok/s) -> probable repli partiel sur CPU, chiffres non comparables aux autres |
| qwen3:30b-a3b | - | - | - | - | - | - | ERREUR: 500 Server Error: Internal Server Error for url: http://localhost:11435/api/generate |

## Anomalies constatees (non corrigees, laissees telles quelles)

- **qwen3:4b, granite3.1-dense:8b, mistral-nemo:12b, deepseek-r1:8b et
  qwen3:30b-a3b : ECHEC.** Plantent des le chargement (avant meme de
  generer un token), y compris sur un prompt trivial comme "Bonjour".
  Erreur upstream Ollama (`failed to allocate buffer ... failed to allocate
  buffer for kv cache`) pour des tailles de : ~140 Go (qwen3:4b), ~72 Go
  (granite3.1-dense:8b), ~156 Go (mistral-nemo:12b), ~64 Go (deepseek-r1:8b),
  ~88 Go (qwen3:30b-a3b). Cause commune : aucun de ces modeles n'a de
  `num_ctx` personnalise dans son Modelfile, donc Ollama tente d'allouer le
  KV-cache pour son contexte max par defaut (128k a 262k tokens selon le
  modele) - bien trop gros pour la VRAM/RAM disponibles sur cette machine.
  **C'est desormais un motif systematique** (5 modeles sur 17 testes, tous
  avec un contexte par defaut >= 128k) plutot qu'un cas isole. Limite
  materielle/configuration, pas un bug du script de benchmark (voir aussi
  la section "Known limits" du README sur les soucis de VRAM/contexte). Le
  correctif standard serait de forcer un `num_ctx` raisonnable (ex. 4096-
  8192) dans la requete - pas fait ici pour rester fidele au "sans limite"
  demande, donc ces modeles restent non mesures.
- **llama3.1:8b, qwen2.5vl:7b et phi4:14b : resultats a prendre avec
  precaution.** Puissance GPU moyenne quasi au repos (13.8 W, 24.4 W et
  34.2 W, contre 56-137 W pour les modeles sains) combinee a une vitesse
  tres faible pour leur taille (11.2, 14.6 et 9.1 tok/s). Signature typique
  d'un repli partiel sur CPU (couches dechargees hors GPU), probablement
  pour la meme raison que ci-dessus (contexte par defaut trop gros forçant
  un partage GPU/CPU au lieu d'un echec total). Le cout/energie calcules
  pour ces trois lignes sous-estiment tres probablement le vrai cout GPU et
  ne sont **pas comparables** aux autres resultats du tableau.
- **qwen2.5:0.5b : mesure peu fiable statistiquement.** La generation s'est
  arretee au bout de seulement 80 tokens / 0.2 seconde (5 echantillons de
  puissance), donc la puissance moyenne mesuree reflete surtout la rampe de
  demarrage du GPU, pas un vrai regime de generation etabli. A reproduire
  avec un prompt qui force une reponse plus longue si une mesure fiable est
  necessaire pour ce modele.

## Cout par pays (USD / 1M tokens generes)

| Modele | France | USA | China | DR Congo | Brazil |
|---|---|---|---|---|---|
| gemma3:1b | 0.0208 | 0.0119 | 0.0064 | 0.0051 | 0.0114 |
| granite3.1-dense:2b | 0.0619 | 0.0355 | 0.0190 | 0.0151 | 0.0340 |
| qwen2.5:3b | 0.0418 | 0.0239 | 0.0128 | 0.0102 | 0.0230 |
| gemma3:4b | 0.0854 | 0.0490 | 0.0262 | 0.0208 | 0.0470 |
| llama3.1:8b | 0.0997 | 0.0572 | 0.0306 | 0.0243 | 0.0549 |
| minicpm-v:latest | 0.1021 | 0.0586 | 0.0313 | 0.0249 | 0.0562 |
| qwen2.5vl:7b | 0.1356 | 0.0777 | 0.0416 | 0.0330 | 0.0746 |
| qwen3.5:9b | 0.2033 | 0.1165 | 0.0623 | 0.0495 | 0.1118 |
| gemma4:latest | 0.1156 | 0.0663 | 0.0355 | 0.0281 | 0.0636 |
| smollm2:135m | 0.0148 | 0.0085 | 0.0045 | 0.0036 | 0.0081 |
| qwen2.5:0.5b | 0.0081 | 0.0047 | 0.0025 | 0.0020 | 0.0045 |
| phi4:14b | 0.3033 | 0.1739 | 0.0930 | 0.0738 | 0.1669 |
