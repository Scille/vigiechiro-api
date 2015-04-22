Api route guide
===============

Introductions
-------------

### verbes HTTP (draft) :

 - GET : récupération d'élément (retourne 200)
 - POST : création d'élément (retourne 201)
 - PATCH : modification unitaire (retourne 200)
 - PUT : modification non unitaire unitaire (retourne 200)
 - DELETE : destruction d'élément (retourn 204)

### Réponses HTTP

 - 200 : ok
 - 201 : ressource créée
 - 204 : la ressource n'est plus disponible
 - 404 : la ressource n'existe pas
 - 422 : paramêtres de la requête invalides
 - 500 : erreur interne au serveur


Utilisateurs
------------


### Lister les utilisateurs

`GET /utilisateurs`

**Parameters**

Nom          |  type   | Requis | Description
-------------|---------|--------|-------------
 page        | integer |  non   | Page courante
 max_results | integer |  non   | Nombre de résultats par page (défaut 40, max 100)
 q           | string  |  non   | Filtre de recherche

**Response**
```
[
    {
        "_id": "54ba5dfd1d41c83768e76fc2",
        "_created": "2015-01-17T13:05:01Z",
        "_updated": "2015-01-17T13:05:01Z",
        "_etag": "7b3cad09dd2f14a713a7d7710744b51ef10e2048",
        "email": "user@github.com",
        "pseudo": "user",
        "nom": "Doe",
        "prenom": "John",
        "adress": "87th Octal street Neverland"
        "telephone": "+33 6 78 32 28 88",
        "organisation": "MNHN",
        "professionnel": true,
        "donnees_publiques": true,
        "commentaire": "There once...",
        "role": "Observateur",
    }
]
```


### Consulter un utilisateur

`GET /utilisateurs/#id`

**Response**
```
{
    "_id": "54ba5dfd1d41c83768e76fc2",
    "_created": "2015-01-17T13:05:01Z",
    "_updated": "2015-01-17T13:05:01Z",
    "_etag": "7b3cad09dd2f14a713a7d7710744b51ef10e2048",
    "email_public": "user@github.com",
    "pseudo": "user",
    "nom": "Doe",
    "prenom": "John",
    "adress": "87th Octal street Neverland"
    "telephone": "+33 6 78 32 28 88",
    "organisation": "MNHN",
    "professionnel": true,
    "donnees_publiques": true,
    "commentaire": "There once...",
    "role": "Observateur",
}
```

### Consulter son propre profil

`GET /moi`

**Response**
```
{
    "_id": "54ba5dfd1d41c83768e76fc2",
    "_created": "2015-01-17T13:05:01Z",
    "_updated": "2015-01-17T13:05:01Z",
    "_etag": "7b3cad09dd2f14a713a7d7710744b51ef10e2048",
    "email": "user@github.com",
    'email_publique': "user@github.com",
    "pseudo": "user",
    "nom": "Doe",
    "prenom": "John",
    "adress": "87th Octal street Neverland"
    "telephone": "+33 6 78 32 28 88",
    "organisation": "MNHN",
    "professionnel": true,
    "donnees_publiques": true,
    "commentaire": "There once...",
    "role": "Observateur",
}
```


### Modifier son propre profil

`PATCH /moi`

**Input**

Nom               |  Type   | Requis | Description
------------------|---------|--------|-------------
pseudo            | string  |  non   |
email             | string  |  non   |
email_publique    | boolean |  non   |
nom               | string  |  non   |
prenom            | string  |  non   |
telephone         | string  |  non   |
adresse           | string  |  non   |
commentaire       | string  |  non   |
organisation      | string  |  non   |
professionnel     | boolean |  non   |
donnees_publiques | boolean |  non   |


### Modifier un utilisateur

`PATCH /utilisateurs/#id`

**Accès**

Administrateur seulement

**Input**

Nom               |  Type   | Requis | Description
------------------|---------|--------|-------------
role              | string  |  non   | nouveau role : `Administrateur`, `Validateur` ou `Observateur`
pseudo            | string  |  non   |
email             | string  |  non   |
email_publique    | boolean |  non   |
nom               | string  |  non   |
prenom            | string  |  non   |
telephone         | string  |  non   |
adresse           | string  |  non   |
commentaire       | string  |  non   |
organisation      | string  |  non   |
professionnel     | boolean |  non   |
donnees_publiques | boolean |  non   |


Protocoles
----------

### Lister les protocoles

`GET /protocoles`

**Parameters**

Nom          |  type   | Requis | Description
-------------|---------|--------|-------------
 page        | integer |  non   | Page courante
 max_results | integer |  non   | Nombre de résultats par page (défaut 40, max 100)
 q           | string  |  non   | Filtre de recherche


### Lister les protocoles d'un utilisateur

`GET /utilisateurs/#id/protocoles`

`GET /moi/protocoles`

**Parameters**

Nom          |  Type   | Description
-------------|---------|-------------
 type        | string  | `tous`, `valide` ou `en_attente`
 sort        | string  | Classement par `nom` ou `date_rejoin`
 direction   | string  | Classement `asc` ou `desc`

**Response**
```
[
    {
        'valide': True,
        ...
    }
]
```

### Rejoindre un protocole

`PUT /moi/protocoles/#id`


### Lister les observateur d'un protocole

`GET /protocoles/#protocole_id/observateurs`

**Input**

Nom               |  Type   | Description
------------------|---------|-------------
type              | string  | 'TOUS' (défaut), 'VALIDES', 'A_VALIDER'

Note : si #protocole_id est mis à 'tous', la liste se fera sur tous les protocoles


### Valider un observateur dans un protocole

`PUT /protocoles/#protocole_id/observateurs/#observateur_id`

**Accès**

Administrateur seulement


### Supprimer un observateur d'un protocole

`DELETE /protocoles/#protocole_id/observateurs/#observateur_id`

**Accès**

Administrateur seulement


### Créer un protocole

`POST /protocoles`

**Accès**

Administrateur seulement


### Modifier un protocole

`PATCH /protocoles/#id`

**Accès**

Administrateur seulement


Taxons
------

### Lister les taxons

`GET /taxons`

**Parameters**

Nom          |  type   | Requis | Description
-------------|---------|--------|-------------
 page        | integer |  non   | Page courante
 max_results | integer |  non   | Nombre de résultats par page (défaut 40, max 100)
 q           | string  |  non   | Filtre de recherche

**Response**
```
[
    {
        ...
    }
]
```

### Consulter un taxon

`GET /taxons/#id`

**Response**
```
{
    ...
}
```


### Créer un taxon

`POST /taxons`

**Accès**

Administrateur seulement


### Modifier un taxon

`PATCH /taxons/#id`

**Accès**

Administrateur seulement


Sites
-----

### Lister les sites

`GET /sites`

**Parameters**

Nom          |  type   | Requis | Description
-------------|---------|--------|-------------
 page        | integer |  non   | Page courante
 max_results | integer |  non   | Nombre de résultats par page (défaut 40, max 100)
 q           | string  |  non   | Filtre de recherche
 observateur | objectid|  non   | N'afficher les site que d'un seul observateur
 protocole   | objectid|  non   | N'afficher les site que d'un seul protocole
 grille_stoc | objectid|  non   | N'afficher les site que d'une seule grille_stoc

**Response**
```
200
{
    '_items': [
        {
            ...
        }
    ]
}
```


### Lister ses propres sites

`GET /moi/sites`

Raccourcis vers la route `GET /sites/` avec param observateur définit à l'utilisateur courant.


### Lister les sites d'un protocole

`GET /protocole/#id/sites`

Raccourcis vers la route `GET /sites/` avec param protocole définit à `#id`.


### Créer un site

`POST /sites`

**Input**

Nom                         |  Type   | Requis | Description
----------------------------|---------|--------|-------------
titre                       | string  |  oui   |
protocole                   | objectid|  oui   |
commentaire                 | string  |  non   |
grille_stoc                 | objectid|  non   |
justification_non_aleatoire | string  |  non   |

**Accès**

Observateur enregistré et validé auprès du protocole spécifié

**Response**
```
201
{
    ...
}
```


### Consulter un site

`GET /sites/#id`

**Response**
```
200
{
    ...
}
```


### Modifier un site

`PATCH /sites/#id`

**Input**

Nom               |  Type   | Requis | Description
------------------|---------|--------|-------------
commentaire       | string  |  non   |
observateur       | objectid|  non   | accès seulement pour administrateur
verrouille        | boolean |  non   | accès seulement pour administrateur

**Accès**

 - si non verrouillé : Administrateur et propriétaire
 - si verrouillé : Administrateur seulement


## Ajouter des localités

`PUT /sites/#id/localites`

**Input**

Nom               |  Type              | Requis | Description
------------------|--------------------|--------|-------------
localites         | dict               | oui    |

**Accès**

 - si non verrouillé : Administrateur et propriétaire
 - si verrouillé : Administrateur seulement


## Ajouter un habitat à une localité

`PUT /sites/#id/localites/#localite_id/habitat`

**Input**

Nom               |  Type       | Description
------------------|-------------|-------------
stoc_principal    | schema_stoc |
stoc_secondaire   | schema_stoc |

        'schema': {
            'date': {'type': 'datetime'},
            'stoc_principal': {
                'type': 'dict',
                'schema': STOC_SCHEMA
            },
            'stoc_secondaire': {
                'type': 'dict',
                'schema': STOC_SCHEMA
            }

**Accès**

Administrateur et propriétaire

## Supprimer toutes les localités

`DELETE /sites/#id/localites`

**Accès**

 - si non verrouillé : Administrateur et propriétaire
 - si verrouillé : Administrateur seulement


Participations
--------------

### Lister les participations

`GET /participations`

**Parameters**

Nom          |  type   | Requis | Description
-------------|---------|--------|-------------
 page        | integer |  non   | Page courante
 max_results | integer |  non   | Nombre de résultats par page (défaut 40, max 100)
 q           | string  |  non   | Filtre de recherche

**Response**
```
[
    {
        ...
    }
]
```


### Lister ses propres participations

`GET /moi/participations`

**Parameters**

Nom          |  type   | Requis | Description
-------------|---------|--------|-------------
 page        | integer |  non   | Page courante
 max_results | integer |  non   | Nombre de résultats par page (défaut 40, max 100)
 q           | string  |  non   | Filtre de recherche

**Response**
```
[
    {
        ...
    }
]
```


### Consulter une participation

`GET /participations/#id`

**Response**
```
{
    ...
}
```


### Créer une participation

`POST /site/#site_id/participations`

**Input**

Nom                    |  Type   | Requis | Description
-----------------------|---------|--------|-------------
numero                 | integer |  oui   | draft : à terme le numero sera déterminé automatiquement par l'api
date_debut             | datetime|  oui   |
date_fin               | datetime|  non   |
commentaire            | string  |  non   |
donnees                | objectid|  non   | liens vers des fichiers uploadés (ta, tc ou données audio)
meteo                  | dict    |  non   |
meteo.temperature_debut| integer |  non   |
meteo.temperature_fin  | integer |  non   |
meteo.vent             | string  |  non   | NUL', 'FAIBLE', 'MOYEN' ou 'FORT'
meteo.couverture       | string  |  non   | '0-25', '25-50', '50-75' ou '75-100'
configuration          | dict    |  oui   | configuration contenant des champs variables en fonction du type de protocole

**Response**
```
201
{
    ...
}
```
**Accès**

Observateur validé auprès d'un protocole et disposant d'un site verrouillé


### Modifier une participation

`PATCH /participations/#id`

**Input**

Nom                    |  Type   | Requis | Description
-----------------------|---------|--------|-------------
date_debut             | datetime|  non   |
date_fin               | datetime|  non   |
commentaire            | string  |  non   |
meteo                  | dict    |  non   |
meteo.temperature_debut| integer |  non   |
meteo.temperature_fin  | integer |  non   |
meteo.vent             | string  |  non   | NUL', 'FAIBLE', 'MOYEN' ou 'FORT'
meteo.couverture       | string  |  non   | '0-25', '25-50', '50-75' ou '75-100'
configuration          | dict    |  non   | configuration contenant des champs variables en fonction du type de protocole

**Accès**

Administrateur et observateur ayant créé la participation


### Accèder aux pièce jointes de la participation

`GET /participations/#id/pieces_jointes`

**Response**

```
200
{
    'pieces_jointes': [
        ...
    ]
}
```

**Accès**

Administrateur et observateur ayant créé la participation


### Ajouter des pièce jointes à la participation

`PUT /participations/#id/pieces_jointes`

**Input**

Nom                    |  Type   | Requis | Description
-----------------------|---------|--------|-------------
pieces_jointes         | list    |  oui   |
pieces_jointes[x]      | ojectid |        | lien vers une ressource fichier dont l'upload est terminé de type `image/bmp`, `image/png`, `image/jpg` ou bien `image/jpeg`

**Accès**

Administrateur et observateur ayant créé la participation


### Ajouter un message dans la participation

`PUT /participation/#id/messages`

**Input**

Nom     |  Type   | Requis | Description
--------|---------|--------|-------------
message | string  |  oui   |

**Accès**

Administrateur, Validateur et observateur ayant créé la participation


Données
-------

### Lister les données

`GET /donnees`

**Accès**

Si propriétaire.donnees_publiques == False : propriétaire, administrateur et validateur
Sinon : tous les observateurs

**Parameters**

Nom          |  type   | Requis | Description
-------------|---------|--------|-------------
 page        | integer |  non   | Page courante
 max_results | integer |  non   | Nombre de résultats par page (défaut 40, max 100)

**Response**
```
[
    {
        "_id": "54ba5dfd1d41c83768e76fc2",
        "_created": "2015-01-17T13:05:01Z",
        "_updated": "2015-01-17T13:05:01Z",
        "_etag": "7b3cad09dd2f14a713a7d7710744b51ef10e2048",
        ...
    }
]
```


### Lister les données d'une participation

`GET /participations/#id/donnees`

**Accès**

Si propriétaire.donnees_publiques == False : propriétaire, administrateur et validateur
Sinon : tous les observateurs

**Parameters**

Nom          |  type   | Requis | Description
-------------|---------|--------|-------------
 page        | integer |  non   | Page courante
 max_results | integer |  non   | Nombre de résultats par page (défaut 40, max 100)
 q           | string  |  non   | Filtre de recherche

**Response**
```
[
    {
        "_id": "54ba5dfd1d41c83768e76fc2",
        "_created": "2015-01-17T13:05:01Z",
        "_updated": "2015-01-17T13:05:01Z",
        "_etag": "7b3cad09dd2f14a713a7d7710744b51ef10e2048",
        ...
    }
]
```


### Créer une donnée pour une participation

`POST /participations/#id/donnees`

**Accès**

Propriétaire de la participation et administrateur.

**Input**

Nom                                    |  Type   | Requis | Description
---------------------------------------|---------|-------------
 proprietaire                          | objectid|  non   | Si non fourni, le propriétaire sera l'utilisateur courant
 commentaire                           | string  |  non   |
 observations                          | list    |  non   | liste des observations faites
 observations[x].temps_debut           | float   |  oui   |
 observations[x].temps_fin             | float   |  oui   |
 observations[x].frequence_mediane     | float   |  oui   |
 observations[x].tadarida_taxon        | objectid|  oui   |
 observations[x].tadarida_probabilite  | integer |  oui   |
 observations[x].tadarida_taxon_autre  | list    |  non   |
 observations[x].tadarida_taxon_autre[y].taxon | objectid | oui |
 observations[x].tadarida_taxon_autre[y].probabilite | integer | oui |

**Response**
```
{
    "_id": "54ba5dfd1d41c83768e76fc2",
    "_created": "2015-01-17T13:05:01Z",
    "_updated": "2015-01-17T13:05:01Z",
    "_etag": "7b3cad09dd2f14a713a7d7710744b51ef10e2048",
    ...
}
```


### Consulter une donnée

`GET /donnees/#id`

**Accès**

Si propriétaire.donnees_publiques == False : propriétaire, administrateur et validateur
Sinon : tous les observateurs

**Response**
```
{
    "_id": "54ba5dfd1d41c83768e76fc2",
    "_created": "2015-01-17T13:05:01Z",
    "_updated": "2015-01-17T13:05:01Z",
    "_etag": "7b3cad09dd2f14a713a7d7710744b51ef10e2048",
    ...
}
```


### Modifier une donnee

`PATCH /donnees/#id`

**Input**

Nom                      |  Type   | Description
-------------------------|---------|-------------
 commentaire                           | string  |  non   |
 probleme                              | string  |  non   |
 observations                          | list    |  non   | liste des observations faites
 observations[x].temps_debut           | float   |  oui   |
 observations[x].temps_fin             | float   |  oui   |
 observations[x].frequence_mediane     | float   |  oui   |
 observations[x].tadarida_taxon        | objectid|  oui   |
 observations[x].tadarida_probabilite  | integer |  oui   |
 observations[x].tadarida_taxon_autre  | list    |  non   |
 observations[x].tadarida_taxon_autre[y].taxon | objectid | oui |
 observations[x].tadarida_taxon_autre[y].probabilite | integer | oui |

**Accès**

Administrateur : commentaire et observations
Propriétaire : commentaire seulement


### Modifier une observation

`PATCH /donnees/#id/observations/#id_observation/`

**Input**

Nom                      |  Type   | Description
-------------------------|---------|-------------
 observateur_taxon       | string  | taxon reconnu par l'observateur
 observateur_probabilite | string  | `SUR`, `PROBABLE`, `POSSIBLE`
 validateur_taxon        | string  | taxon reconnu par le validateur
 validateur_probabilite  | string  | `SUR`, `PROBABLE`, `POSSIBLE`

### Commenter une observation

`PUT /donnees/#id/observations/#id_observation/messages`

**Input**

Nom                 |  Type   | Description
--------------------|---------|-------------
 message            | string  |


Fichiers
--------

### Enregistrer un nouveau fichier

`POST /fichiers`

**Input**

Nom                 |  Type   | Description
--------------------|---------|-------------
 titre              | string  | Nom du fichier
 mime               | string  | Mime type du fichier
 multipart          | boolean | Le fichier va-t-il être uploader en multipart ?
 require_process    | string  | Administrateur seulement, `tadarida_c` ou `tadarida_d`
 lien_donnee        | objectid| Relie le fichier à une donnee
 lien_protocole     | objectid| Relie le fichier à un protocole
 proprietaire       | objectid| L'administrateur peut définir le propriétaire du fichier

Note: si le fichier à uploader fait plus de 5mo, il doit être uploader en multipart

**Response : Singlepart upload**
```
201
{
    "titre": "kitten.png",
    "mime": "image/png",
    "proprietaire": "54ba5dfd1d41c83768e76fc2",
    "disponible": False,
    "s3_id": "...",
    "s3_signed_url": "https://vigiechiro.s3.com/..."
}
```

**Response : Multipart upload**
```
201
{
    "titre": "kitten.png",
    "mime": "image/png",
    "proprietaire": "54ba5dfd1d41c83768e76fc2",
    "disponible": False,
    "s3_id": "...",
    "s3_multipart_upload_id": "..."
}
```

Note : le lien fourni a une validité de 10s


### Multipart : Recupérer l'url S3 d'upload d'une partie

`PUT /fichiers/#id/multipart`

**Parameters**

Nom          |  Type   | Description
-------------|---------|-------------
 part_number | integer | partie à uploader (commençant à 1)

**Response**
```
200
{
    "s3_signed_url": "https://vigiechiro.s3.com/..."
}
```

**Accès**

Créateur du fichier seulement

Note: cette fonctionnalité n'est accessible qui si le fichier a été créé 
comme multipart ("s3_multipart_upload_id" != "") et tant que la fin de
l'upload n'a pas été terminé ("s3_upload_done" == False)

Note : le lien fourni a une validité de 10s


### Annuler l'upload du fichier

`DELETE /fichiers/#id`

**Response**
```
204
{
}
```

**Accès**

Créateur du fichier seulement

Note: cette fonctionnalité n'est accessible qui si l'upload n'a pas été 
terminé ("s3_upload_done" == False)


### Signifier la fin de l'upload du fichier

`POST /fichiers/#id`

**Multipart : Input**

Nom                    |  Type   | Description
-----------------------|---------|-------------
 parts                 | list    | list des partie uploadées
 parts[x][part_number] | integer | index de la partie
 parts[x][etag]        | etag    | etag de la partie

Note : dans le cas d'un singlepart upload, pas d'input n'est requis

**Response**
```
200
{
    "titre": "kitten.png",
    "mime": "image/png",
    "proprietaire": "54ba5dfd1d41c83768e76fc2",
    "disponible": False,
    "s3_id": "..."
}
```

**Accès**

Créateur du fichier seulement

Note: cette fonctionnalité n'est accessible qui si l'upload n'a pas été 
terminé ("s3_upload_done" == False)


### Accèder aux metadonnées d'un fichier

`GET /fichiers/#id`

**Accès**

Si propriétaire.donnees_publiques == False : propriétaire, administrateur et validateur
Sinon : tous les observateurs

**Response**
```
200
{
    "titre": "kitten.png",
    "mime": "image/png",
    "proprietaire": "54ba5dfd1d41c83768e76fc2",
    "disponible": True,
    "s3_id": "..."
}
```


### Accèder au contenu d'un fichier

`GET /fichiers/#id/acces`

**Parameters**

Nom          |  Type   | Description
-------------|---------|-------------
 redirection | boolean | redirige vers le fichier au lieu de renvoyer le lien d'accès

**Accès**

Si propriétaire.donnees_publiques == False : propriétaire, administrateur et validateur
Sinon : tous les observateurs

**Response (redirection=False)**
```
200
{
    "s3_signed_url": "https://vigiechiro.s3.com/..."
}
```

Note : le lien fourni a une validité de 10s


Actualités
----------

### Lister les actualités de l'utilisateur

`GET /moi/actualites`

**Parameters**

Nom          |  Type   | Requis | Description
-------------|---------|--------|-------------
 page        | integer |  non   | Page courante
 max_results | integer |  non   | Nombre de résultats (défaut 20, max 100)

Note: les actualités sont retournées en commençant par les plus récentes

**Response**
```
{
    '_items': [
        {
            ...
        }
    ]
}
```

### Lister les actualités de validation

`GET /actualites/validations`

**Parameters**

Nom          |  Type   | Requis | Description
-------------|---------|--------|-------------
 page        | integer |  non   | Page courante
 max_results | integer |  non   | Nombre de résultats (défaut 20, max 100)
 type        | string  |  non   | `TOUS` (défaut), `VALIDES` ou `A_VALIDER`
 protocole   | objectid|  non   | Ne liste que les validations du protocole

Note: les actualités sont retournées en commençant par les plus récentes


Grille STOC
-----------

### Retrouver les grille STOC contenues dans un rectangle

`GET /grille_stoc/rectangle`

**Parameters**

Nom          |  Type   | Requis | Description
-------------|---------|--------|-------------
 sw_lat      |  float  |  oui   | latitude du point sud ouest
 sw_lng      |  float  |  oui   | longitude du point sud ouest
 ne_lat      |  float  |  oui   | latitude du point nord est
 ne_lng      |  float  |  oui   | longitude du point nord estmax_results
 page        | integer |  non   | Page courante
 max_results | integer |  non   | Nombre de résultats par page (défaut 40, max 40)

**Response**
```
{
    '_items': [
        {'_id': '54de89c31d41c80dc8e9bd88', 'numero': '590018',
        'centre': {'type': 'Point', 'coordinates': [2.181529126, 51.0245531]}}
    ],
    '_meta': {'page': 1, 'total': 1, 'max_results': 20}
}
```


### Retrouver la grille STOC contenues dans un cercle

`GET /grille_stoc/cercle`

**Parameters**

Nom          |  Type   | Requis | Description
-------------|---------|--------|-------------
 lat         |  float  |  oui   | latitude du point
 lng         |  float  |  oui   | longitude du point
 r           |  float  |  oui   | rayon en mètres

**Response**
```
{
    ...
}
```
