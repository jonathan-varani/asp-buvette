# ASP Buvette — Spécification V1

Planning public des matchs du weekend de l'ASP Basket Ste Marie aux Chênes, avec le
responsable de buvette de chaque match à domicile.

## 1. Objectif
- Afficher, par weekend, **tous** les matchs du club (domicile et extérieur, amicaux inclus).
- Pour chaque match à domicile, afficher le **responsable de la buvette** (Prénom Nom).
- Les responsables du club saisissent/modifient ce responsable via une page admin protégée.

Hors V1 : formulaire permettant à un parent de s'inscrire lui-même (V2).

## 2. Utilisateurs
| Rôle | Accès | Actions |
|---|---|---|
| Public | Sans login | Consulter le planning, naviguer entre weekends, consulter l'historique |
| Admin | Mot de passe unique partagé | Affecter / modifier / retirer le responsable d'un match domicile |

## 3. Source des données
- Club FFBB : `https://competitions.ffbb.com/ligues/ges/comites/0057/clubs/ges0057030`
- Découverte automatique : club → équipes → championnat/poule de chaque équipe → matchs.
- La FFBB est protégée (anti-bot, coupe si débit trop élevé) : le scraping tourne **sur le PC de
  Jonathan**, pas sur GitHub Actions, comme `FFBB_Agenda`.
- Réutilisation de `FFBB_Agenda/scraper_http.py` (`scrape_poule`, lecture du JSON Next.js `__next_f`),
  2 requêtes en parallèle maximum.
- **Risque** : les pages d'équipe sont derrière un défi anti-bot. Test à faire en premier depuis le PC.
  Repli : liste manuelle des poules par saison (comme `FOCUS` dans `scrape_focus.py`).

## 4. Synchronisation
- Tâche planifiée Windows « ASP Buvette - sync », **toutes les 4 h**.
- Script PowerShell (modèle : `FFBB_Agenda/run_focus.ps1`) : lance le scraper, journalise dans `logs\`.
- Upsert dans Supabase par clé de match stable ; **ne touche jamais aux responsables**.
- Si un scrape échoue ou renvoie une poule vide : données existantes conservées.
- Un match déplacé (date/heure) garde son responsable (clé = id FFBB du match, pas la date).
- Un match disparu de la FFBB est marqué `annule`, pas supprimé (le responsable reste visible en admin).

## 5. Règles métier
- **Domicile** = `equipe1` contient « STE MARIE AUX CHENES » (équipes - 1, - 2, etc. incluses).
- Matchs amicaux : affichés comme les autres, avec une mention « Amical ».
- Un seul responsable par match : un prénom et un nom (pas de téléphone).
- Weekend = samedi + dimanche (vendredi soir et lundi : à valider, voir §10).
- Affichage par défaut : weekend en cours (ou le prochain si on est en semaine après le dimanche).
- Historique consultable via navigation weekend précédent/suivant et sélecteur de date.

## 6. Modèle de données (Supabase)
**`matches`**
| Colonne | Type | Note |
|---|---|---|
| `id` | text PK | id FFBB du match (ou clé composite poule+journée+équipes si absent) |
| `date` | date | |
| `heure` | time | nullable |
| `equipe1`, `equipe2` | text | noms FFBB |
| `categorie` | text | ex. U15M, Seniors F |
| `competition` | text | championnat + poule |
| `salle` | text | nullable |
| `score1`, `score2` | int | nullable |
| `amical` | bool | |
| `domicile` | bool | calculé à l'import |
| `statut` | text | `prevu` / `joue` / `annule` |
| `updated_at` | timestamptz | |

**`buvette`**
| Colonne | Type | Note |
|---|---|---|
| `match_id` | text PK, FK → matches | |
| `prenom`, `nom` | text | |
| `updated_at` | timestamptz | |

Sécurité (RLS) : lecture publique (anon) sur `matches` et `buvette` ; aucune écriture anon.
Écriture `matches` : clé service role (PC uniquement, dans `.env`).
Écriture `buvette` : uniquement via les fonctions RPC `buvette_set` / `buvette_clear`, qui vérifient le
mot de passe admin (hash bcrypt dans `private.admin_config`, jamais exposé). Pas d'Edge Function nécessaire.
Le mot de passe est défini par `admin_set_password` (réservé à la clé service_role).

## 7. Composants
1. **Scraper** (Python, PC) : découverte équipes/poules, extraction matchs, upsert Supabase.
2. **Supabase** (projet `asp-buvette`, eu-west-3) : tables, RLS, fonctions RPC admin. Config dans `supabase.config.json`.
3. **Page publique** `index.html` : planning weekend, mobile first, sans login.
4. **Page admin** `admin.html` : saisie du mot de passe (conservé en sessionStorage), liste des
   matchs domicile à venir, champs Prénom/Nom par match, boutons Enregistrer/Effacer.
5. **Hébergement** : GitHub Pages sur `basket.buvette.varai.fr` (CNAME, comme `basket.varai.fr`).

## 8. Écrans
**Public**
- En-tête : « Weekend du 18–19 octobre » + flèches précédent/suivant + bouton « Aujourd'hui ».
- Matchs groupés par jour, triés par heure. Carte match : heure, équipe/catégorie, adversaire,
  salle, domicile/extérieur, score si joué.
- Match à domicile : ligne « 🍺 Buvette : Prénom Nom » ou « Buvette : à pourvoir » (en évidence).
- Lisible sur téléphone ; imprimable.

**Admin**
- Même navigation par weekend, uniquement les matchs à domicile modifiables.
- Indicateur des matchs sans responsable.

## 9. Critères d'acceptation V1
- Le planning du weekend s'affiche sans login, avec domicile et extérieur.
- Un responsable saisi en admin apparaît en public immédiatement.
- Le mot de passe incorrect ne permet aucune écriture.
- Après une synchro, un horaire modifié par la FFBB est mis à jour, le responsable est conservé.
- La synchro tourne toutes les 4 h sans intervention et journalise ses échecs.

## 10. Points ouverts (valeurs par défaut retenues)
- Définition du weekend : samedi–dimanche par défaut.
- Nom de domaine : `basket.buvette.varai.fr` (confirmé).
- Notifications en cas d'échec de synchro : journal seulement en V1.
- Mot de passe admin partagé : **actuellement VIDE (provisoire)**. À définir via `admin_set_password` avant toute mise en ligne publique de la page admin.

## 11. Plan de réalisation
1. Test de découverte des équipes/poules depuis le PC (valide ou invalide la source auto).
2. Création du projet Supabase, tables, RLS.
3. Scraper + upsert, puis tâche planifiée 4 h.
4. Edge Function admin.
5. Pages publique et admin.
6. Déploiement GitHub Pages + DNS.
