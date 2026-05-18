# ibestat-mcp

> **Català** | [English](README.en.md) | [Español](README.es.md)

Un servidor MCP que dona als LLMs accés analític a més de 3.730 datasets públics de les Illes Balears — turisme, població, economia, habitatge, medi ambient i més.

Construït sobre l'API eDades d'[IBESTAT](https://ibestat.es). Dissenyat per a [Claude Desktop](https://claude.ai), [Claude Code](https://claude.com/claude-code) i qualsevol client compatible amb MCP.

## Taula de continguts

- [De dades en brut a coneixement](#de-dades-en-brut-a-coneixement)
- [Instal·lació](#installació)
- [Configuració](#configuració)
- [Eines](#eines)
- [Prompts MCP](#prompts-mcp)
- [Nota sobre l'idioma de les dades](#nota-sobre-lidioma-de-les-dades)
- [Resolució de problemes](#resolució-de-problemes)
- [Desenvolupament](#desenvolupament)
- [Llicència](#llicència)

## De dades en brut a coneixement

L'API eDades ofereix dades estadístiques potents, però navegar-hi requereix IDs de datasets, codis críptics i múltiples endpoints. ibestat-mcp salva aquesta distància:

| API en brut | ibestat-mcp |
|-------------|-------------|
| No hi ha catàleg navegable — necessites els IDs dels datasets | **Arbre temàtic** amb 52 categories que el LLM pot explorar |
| Els codis de dimensió són críptics (`07040`, `_T`, `A`) | **Exploració de codis** que revela el significat i l'estructura dels codis |
| Filtrar requereix IDs de dimensions i codis exactes | **Inspecció de datasets** que exposa dimensions, valors vàlids i referències a codelists |
| No hi ha manera de descobrir datasets relacionats | **Descobriment creuat** mitjançant temes compartits i cerca per paraula clau |
| Les metadades estructurals requereixen crides API separades | **Caching automàtic** de temes, codelists i definicions d'estructura de dades |

El resultat: un LLM pot passar d'una pregunta en llenguatge natural a una resposta basada en dades en una sola conversa — sense que l'usuari conegui cap ID de dataset ni cap endpoint de l'API.

Veure'l en acció: [El turisme genera més residus a les Illes Balears?](examples/waste-tourism-correlation.md) — un exemple on el LLM creua dos datasets independents per descobrir una forta correlació (Pearson r = 0,95).

## Instal·lació

Encara no disponible a PyPI. Instal·la directament des de GitHub:

```bash
pip install git+https://github.com/JavaLavadora/ibestat-mcp.git
```

O per a desenvolupament local:

```bash
git clone https://github.com/JavaLavadora/ibestat-mcp.git
cd ibestat-mcp
pip install -e ".[dev]"
```

## Configuració

### Claude Desktop

Afegeix al teu `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ibestat": {
      "command": "ibestat-mcp"
    }
  }
}
```

Ubicació de l'arxiu de configuració:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Claude Code (CLI)

Afegeix a la configuració del projecte (`.claude/settings.json`):

```json
{
  "mcpServers": {
    "ibestat": {
      "command": "ibestat-mcp"
    }
  }
}
```

O via la CLI:

```bash
claude mcp add ibestat -- ibestat-mcp
```

## Eines

| Eina | Descripció | Caching |
|------|------------|---------|
| `browse_topics` | Navega pel catàleg temàtic d'IBESTAT (52 categories) | Sí |
| `list_datasets_by_topic` | Llista tots els datasets d'una categoria | Sí |
| `search_datasets` | Cerca datasets per paraula clau | No |
| `get_dataset_info` | Obté dimensions, valors de filtre i IDs de codelists | DSD amb cache |
| `get_codelist` | Explora codis jeràrquics (p.ex., Comunitat > Illa > Municipi) | Sí |
| `get_data` | Obté files de dades amb filtres opcionals per dimensió | No |

### Flux de treball recomanat

1. **Navega** -- `browse_topics` per veure quins dominis cobreix IBESTAT
2. **Llista** -- `list_datasets_by_topic` per trobar datasets dins una categoria
3. **Cerca** -- *(alternativa)* `search_datasets` quan ja saps què cerques
4. **Inspecciona** -- `get_dataset_info` per entendre les dimensions i obtenir IDs de codelists
5. **Explora** -- `get_codelist` per descobrir valors de filtre vàlids a tots els nivells jeràrquics
6. **Consulta** -- `get_data` amb filtres precisos descoberts als passos anteriors

### Exemples de prompts

Prova a demanar al teu LLM:

- "Quina era la població de Palma el 2024?"
- "Mostra'm estadístiques de turisme de les Illes Balears"
- "Compara les taxes d'ocupació entre Mallorca, Menorca i Eivissa"
- "Quines són les últimes tendències de preus d'habitatge a les Illes Balears?"
- "Quants turistes van visitar Eivissa l'any passat?"

## Prompts MCP

Cinc prompts integrats ajuden els LLMs a navegar les dades d'IBESTAT sense que l'usuari hagi de conèixer el flux de treball de les eines:

| Prompt | Descripció | Args obligatoris |
|--------|------------|------------------|
| `explore_topic` | Explora un tema estadístic de principi a fi | `topic` |
| `query_dataset` | Consulta un dataset concret per ID | `dataset_id` |
| `compare_municipalities` | Compara dades entre municipis de les Illes Balears | `topic` |
| `time_series` | Mostra tendències al llarg del temps | `topic` |
| `discover_available_data` | Introducció: quines dades té IBESTAT? | *(cap)* |

Tots els prompts accepten un argument opcional `language` (`ca`, `es` o `en`, per defecte `ca`).

## Nota sobre l'idioma de les dades

Totes les eines accepten un paràmetre `language`:

- `ca` -- Català (per defecte). Etiquetes com "Territori", "Poblacio".
- `es` -- Castellà. Etiquetes com "Territorio", "Poblacion".
- `en` -- Anglès. Etiquetes com "Reference area", "Population".

La cerca funciona millor en català o castellà ja que els noms dels datasets estan emmagatzemats en aquests idiomes. Usa `poblacio` en lloc de "population", `turisme` en lloc de "tourism".

## Resolució de problemes

**La cerca no retorna resultats amb termes en anglès**
Els noms dels datasets estan indexats en català/castellà. Usa arrels catalanes: `poblaci` (població), `turisme` (turisme), `atur` (atur), `habitatge` (habitatge). Les coincidències parcials funcionen.

**`get_data` és lent o retorna massa dades**
Sense filtres, es descarreguen totes les observacions — alguns datasets tenen centenars de milers de files. Crida sempre `get_dataset_info` primer, i després passa `filters` per acotar per període de temps, territori, etc.

**Error "IBESTAT service is unavailable"**
L'API d'IBESTAT és un servei públic governamental sense SLA. Espera uns minuts i torna-ho a provar. Si persisteix, comprova que `https://ibestat.es` és accessible des de la teva xarxa.

**Error "Dataset not found"**
L'ID del dataset pot ser incorrecte o el dataset pot haver estat retirat. Usa `search_datasets` per trobar l'ID vàlid actual — copia el camp `id` exactament com es retorna.

**Les claus de filtre semblen ignorar-se (dades sense filtrar)**
Els filtres requereixen IDs de dimensió (`TIME_PERIOD`, `TERRITORIO`) i codis de valor (`07040`, `_T`), no etiquetes llegibles. Usa els camps `id` i `code` de `get_dataset_info`, no `name` ni `label`.

**Els noms de columna i valors no estan en el meu idioma**
El servidor retorna etiquetes en català per defecte. Estableix el paràmetre `language` a `es` per castellà o `en` per anglès.

## Desenvolupament

```bash
pip install -e ".[dev]"
pytest -m "not e2e"   # tests unitaris (ràpids, sense xarxa)
pytest -m e2e         # end-to-end (connecta amb l'API real)
pytest                # tots
```

## Llicència

MIT -- veure [LICENSE](LICENSE)
