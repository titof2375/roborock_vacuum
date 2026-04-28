"""Constants for Roborock Vacuum integration."""

DOMAIN = "roborock_vacuum"

CONF_EMAIL     = "email"
CONF_USER_DATA = "user_data"
CONF_HOME_DATA = "home_data"

UPDATE_INTERVAL_SECONDS = 30

# Statuts Roborock → texte français
VACUUM_STATUS = {
    0:  "Inconnu",
    1:  "En veille",
    2:  "Sommeil",
    3:  "En attente",
    4:  "Nettoyage",
    5:  "Retour à la base",
    6:  "Nettoyage manuel",
    7:  "Chargement",
    8:  "Chargement",
    9:  "Erreur",
    10: "Pause",
    11: "Nettoyage par zone",
    12: "Nettoyage par pièce",
    13: "Mise à jour firmware",
    14: "Localisation",
    15: "Vide du bac",
    16: "Nettoyage vadrouille",
    17: "En attente",
    18: "Retour vadrouille",
    100: "Chargement complet",
}

# Codes d'erreur Roborock
VACUUM_ERRORS = {
    0:  "",
    1:  "Capteur laser bloqué",
    2:  "Collision détectée",
    3:  "Roues glissantes",
    4:  "Capteur de falaise",
    5:  "Batterie faible",
    6:  "Bac plein",
    7:  "Bac manquant",
    8:  "Filtre bloqué",
    9:  "Brosse principale bloquée",
    10: "Bloqué",
    11: "Capteur de charge",
    12: "Zone interdite",
    13: "Mur magnétique",
    14: "Batterie anormale",
    15: "Problème ventilateur",
    16: "Chargeur anormal",
    17: "Capteur de falaise gauche",
    18: "Brosse latérale bloquée",
    19: "Laser poll",
    20: "Décharge PSD",
    21: "Capteur mur",
    22: "Batterie anormale",
}

# Niveaux de ventilateur
FAN_SPEEDS = {
    101: "Silencieux",
    102: "Standard",
    103: "Fort",
    104: "Maximum",
    105: "Mode vadrouille",
}
