# Fabrication avec les machines publiques gratuites

Le workflow `Build installers with free public runners` utilise uniquement les
machines standards GitHub Windows, Linux, Mac Intel et Mac Apple Silicon.
Il ne modifie aucun budget et n'utilise ni machine payante, ni cache Actions,
ni stockage d'artefacts Actions. Les fichiers de livraison transitent par une
release brouillon de ce dépôt.

Le code de l'application reste dans `KakitaBen/MECCG_AUTO_CARD_EDITOR`.
Ce dépôt contient seulement l'orchestration de sa fabrication. Les sorties
détaillées des commandes privées sont écrites dans un fichier temporaire sur
la machine de compilation, sans affichage dans les journaux publics et sans
mise en ligne de ce fichier. En cas d'échec, le journal public indique seulement
l'étape et la classe de l'erreur. Les machines sont temporaires.

## Autorisation de lecture

Le propriétaire doit créer lui-même un jeton GitHub à permissions fines :

- propriétaire `KakitaBen` ;
- uniquement le dépôt `MECCG_AUTO_CARD_EDITOR` ;
- permission **Contents: Read-only**, sans droit d'écriture ;
- expiration limitée.

Enregistrer ce jeton directement dans les secrets Actions de ce dépôt public,
avec le nom `SOURCE_READ_TOKEN`. Ne pas le mettre dans une conversation ou un
fichier du dépôt. Le jeton de publication du dépôt privé n'est pas utilisé ici.
Les fichiers publics sont déposés avec le jeton intégré à cette exécution,
limité au dépôt de téléchargements.

Seul le compte propriétaire peut lancer ces jobs. Il n'y a pas d'exécution sur
pull request, sur une contribution extérieure, ou sur un commit de workflow
fourni par un contributeur. Les accès de checkout ne sont pas conservés dans
les dépôts clonés.

## Exécution

1. Ouvrir Actions, puis `Build installers with free public runners`.
2. Choisir un **commit complet de 40 caractères** du code privé déjà validé.
3. Garder `resources_version` à `v0.59.46` tant que les illustrations sont
   identiques à cette référence. Le workflow compare leurs arbres Git.
4. Décocher `check_only` pour construire. En le laissant coché, seule la
   disponibilité d'une machine publique et les tests de l'orchestration sont
   contrôlés ; aucun code privé n'est lu.

Les seize lots d'illustrations sont repris de la livraison complète déjà
préparée, après vérification de leurs tailles et de leurs SHA-256. Il n'y a pas
de nouveau téléchargement Git LFS. Le classeur, les mises en page, les fonds,
les polices et le changelog sont toujours reconstruits depuis le commit choisi.
Si les illustrations ont changé, l'exécution s'arrête et exige une nouvelle
référence vérifiée plutôt que de réutiliser des images différentes.

Les programmes sont construits nativement. Leurs installateurs sont exécutés
et vérifiés avec les ressources complètes, les polices privées et les
certificats HTTPS embarqués. Les preuves JSON ne sont déposées qu'après succès.
La release reste en brouillon jusqu'à sa validation. Les releases déjà publiques
ne peuvent pas être remplacées par cette chaîne.

Depuis v0.60.20, chaque lot inclut aussi une archive `.update.zip` indexée pour
les mises à jour depuis l’application. Les anciens lots d’illustrations sont
vérifiés et indexés un par un sans modifier leurs archives d’origine. Le README
et la configuration publique du service accompagnent les ressources communes.

Les premières versions restent des candidats non signés. Une diffusion Mac
sans avertissement Gatekeeper demande encore signature et notarisation Apple.
