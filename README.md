# Betclic Portugal · Tickets Discord

Bot simple en portugais du Portugal, conçu pour un seul serveur Discord.

## Utilisation

- `/painel` : un administrateur publie le panneau dans le salon où il lance la commande.
- `📩 Contactar a equipa` : crée un salon privé pour le membre et le rôle support. Les administrateurs Discord y ont aussi accès.
- `🎟️ Assumir` : un membre du support prend le ticket en charge. Les autres agents gardent accès au ticket mais ne peuvent pas remplacer ce responsable via le bouton.
- `🔒 Fechar` : le membre conserve l'accès au ticket en lecture seule. L'équipe peut encore y écrire.
- `🔓 Reabrir` : l'équipe rétablit l'écriture du membre.
- `🗑️ Eliminar` : l'équipe supprime un ticket fermé, après confirmation. Suppression définitive sans export de l'historique.

Un seul ticket par membre, y compris fermé, tant qu'il n'est pas supprimé. Pour en ouvrir un autre, l'équipe doit supprimer l'ancien ou le rouvrir. Un membre qui est aussi support/administrateur conserve les privilèges de ce rôle.

## GitHub

Créer un dépôt séparé, par exemple `betclic-portugal-tickets`. Mettre `bot.py`, `requirements.txt` et `Dockerfile` à la racine, ainsi que ce README et les fichiers exemples si souhaité. Ne pas remplacer le dépôt du bot BiggerZ.

## Discord

1. Créer une application et un bot sur https://discord.com/developers/applications. Nom suggéré : `Betclic Portugal`. Définir l'avatar Betclic autorisé dans le portail.
2. Inviter le bot avec les scopes `bot` et `applications.commands`.
3. Donner au bot : View Channels, Send Messages, Embed Links, Read Message History, Manage Channels et Manage Roles. Manage Roles sert à définir les permissions privées des tickets. Placer son rôle au-dessus du rôle support. Le bot n'a pas besoin d'Administrator.
4. Créer une catégorie dédiée aux tickets et un rôle support distinct de `@everyone`. Donner le rôle support uniquement à l'équipe. Vérifier que les permissions de la catégorie ne bloquent pas le bot.
5. Activer le mode développeur Discord puis copier les identifiants du serveur, de la catégorie et du rôle support. Copier le token depuis la section Bot du portail développeur.

Aucun intent privilégié à activer : ni Message Content, ni Server Members, ni Presence.

## Railway

Créer un service depuis le dépôt GitHub. Le Dockerfile lance `python bot.py`.

| Variable | Valeur |
| --- | --- |
| `DISCORD_TOKEN` | Token du nouveau bot Betclic Portugal |
| `DISCORD_GUILD_ID` | Identifiant du serveur Betclic Portugal |
| `TICKET_CATEGORY_ID` | Identifiant de la catégorie réservée aux tickets |
| `SUPPORT_ROLE_ID` | Identifiant du rôle de l'équipe support |

Pas de guillemets autour des valeurs. Ne jamais mettre le token dans GitHub. `.env.example` est seulement un exemple et n'est pas chargé automatiquement par Python.

Garder **une seule instance / replica**, désactiver Serverless et ne pas lancer le même bot ailleurs. Pour une mise à jour sans chevauchement, arrêter l'ancien déploiement avant de démarrer le nouveau : le verrou anti-doublon est local au processus. Aucun domaine public, port HTTP, healthcheck HTTP ou volume Railway requis. Redémarrage On Failure conseillé.

Le bot conserve l'auteur, l'état et le responsable dans le sujet de chaque salon Discord. Ne pas modifier ces sujets ni déplacer les tickets hors de la catégorie configurée. Les boutons continuent à fonctionner après un redémarrage grâce à leurs identifiants persistants.

Une fois le déploiement démarré, lancer `/painel` dans le salon de contact souhaité. La commande publie un nouveau panneau à chaque utilisation : ne la relancer que si besoin.

## Vérification avant ouverture aux membres

Avec un membre sans rôle support : créer un ticket, vérifier qu'un autre membre ne le voit pas et que les boutons de gestion refusent l'accès. Avec le support : prendre en charge, fermer, rouvrir puis fermer/supprimer un ticket de test. Redémarrer le bot et vérifier un ancien panneau et un ticket existant.

La vérification locale fournie ne remplace pas ce test réel sur Discord : aucun token client n'a été utilisé pour développer ce projet.

## Références techniques

- https://discordpy.readthedocs.io/en/stable/interactions/api.html
- https://discordpy.readthedocs.io/en/stable/api.html
- https://docs.railway.com/deployments/serverless
