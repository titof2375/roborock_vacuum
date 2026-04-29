# Roborock Vacuum — Intégration HACS pour Home Assistant

Intégration custom pour contrôler vos aspirateurs Roborock depuis Home Assistant via le cloud Roborock.

Développée pour les modèles non supportés par l'intégration officielle (ex : QV35A).

---

## Fonctionnalités

- Authentification par **email + code OTP** (aucun mot de passe stocké)
- **Contrôle complet** de l'aspirateur :
  - Démarrer / Arrêter / Pause
  - Retour à la base
  - Localisation (find me)
  - Réglage de la vitesse du ventilateur
- **Capteurs** créés automatiquement :
  - Batterie (%)
  - Statut (Nettoyage, En veille, Chargement…)
  - Surface nettoyée (m²)
  - Durée du nettoyage (min)
  - Code erreur
  - Totaux cumulés (surface, durée, nombre de nettoyages)
- Rafraîchissement automatique toutes les **30 secondes**
- Compatible avec plusieurs aspirateurs sur le même compte

---

## Installation via HACS

1. HACS → ⋮ → **Dépôts personnalisés**
2. URL : `https://github.com/titof2375/roborock_vacuum`  
   Catégorie : **Intégration**
3. Installer **Roborock Vacuum**
4. **Redémarrer Home Assistant**
5. Paramètres → Intégrations → **+ Ajouter** → chercher **Roborock Vacuum**

---

## Configuration

### Étape 1 — Email
Saisissez votre adresse email du compte Roborock.  
Un code de vérification à 6 chiffres est envoyé par email.

### Étape 2 — Code OTP
Saisissez le code reçu dans votre boîte mail.  
L'intégration se connecte et détecte automatiquement vos aspirateurs.

---

## Modèles testés

| Modèle | Statut |
|--------|--------|
| Roborock QV35A | ✅ Testé |

---

## Dépannage

- Vérifiez les journaux dans **Paramètres → Système → Journaux** et filtrez sur `roborock_vacuum`
- Assurez-vous d'avoir redémarré HA après installation HACS
- Le code OTP expire après quelques minutes — relancez la configuration si besoin

---

## Versions

| Version | Notes |
|---------|-------|
| 1.0.1 | Fix compatibilité python-roborock (imports lazy) |
| 1.0.0 | Version initiale |
