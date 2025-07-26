from app.moteur_calcul.loader  import load_donnees_saisie , load_rendement_ecs , get_puissance_ventilation
from app.moteur_calcul.loader  import load_typologie_data , load_temperature_data , load_coefficients_gv
from app.moteur_calcul.hypotheses.conversion import conversion
from app.moteur_calcul.conso_initial import convertir_consommation  
from app.moteur_calcul.conso_initial import calcul_carbone_et_cout_sql
from app.models.output import output  # à adapter selon ton arborescence
from app.db.database import get_session
from sqlalchemy import text
from app.db.database import engine

Capacité_thermique_volumique_eau = 1.162
temperature_chaude = 60 
Nombres_semaines_chauffage =  26
couverture_PAC_Chauffage = 0,6
couverture_PAC_ECS = 0,6
Taux_EnR_mix_E_national_Elec  = 26/100
Taux_EnR_mix_E_national_Gaz = 1,6 / 100

SLUG_TO_ENERGIE = {
        "gn": "Gaz naturel",
        "gbp": "Gaz butane/propane",
        "fioul": "Fioul",
        "charbon": "Charbon",
        "bp" : "Bois plaquettes" , 
        "bg": "Bois granulés", 
        "rcu" : "Réseau de chaleur" ,
        "rfu" : "Réseau de froid" , 
        "aucune" : "Aucune"   }

SLUG_MASQUE = {
    "batiment_moins_lh": "Bâtiment à moins de L=H",
    "vegetation_dense_haute": "Végétation dense et haute",
    "vegetation_peu_impactante": "Végétation peu impactante",
    "aucun": "Aucun"
}


SLUG_TO_TYPE_ECS = {
    "inco": "Inconnu",
    "elec": "Electrique",
    "fioul": "Fioul",
    "gaz": "Gaz",
    "bois": "Bois",
    "pac": "PAC",
    "geo": "Géothermie",
    "rcu": "rcu"}


SLUG_TO_PRODUCTION_ECS = {
        "pc": "production collective",
        "pi": "production individuelle" }

SLUG_USAGE_THERMIQUE = {
    "ch": "chauffage",
    "ch_ecs": "chauffage + ecs",
    "ch_clim": "chauffage + clim",
    "ch_clim_ecs": "chauffage + clim + ecs"
}

SLUG_TO_STRATEGIE = {
    "be": "Aucune (Bâtiment existant)",
    "bn": "Aucune (Bâtiment neuf)",
    "rl": "Rénovation légère (Quick Win)",
    "ra": "Rénovation d'ampleur (grand saut)"
}

SLUG_TO_TOITURE = {
    "te": "Terrasse",
    "it": "Inclinée tuiles",
    "iba": "Inclinée bac acier ou autres",
    "iza": "Inclinée zinc/ardoise (type bâtiment haussmannien ou similaire)"
}

SLUG_TO_SITUATION = {
    "urbain": "Urbain",
    "p_urbain": "Péri-urbain",
    "rural": "Rural"
}

SLUG_PATRIMOINE = {
    "so": "Sans objet",
    "bc": "Bâtiment classé",
    "abf": "Périmètre ABF / abords des monuments historiques"
}




class ProjetCalcul:
    def __init__(self):
        self.id_projet = self._recuperer_dernier_id_projet()
        self.donnees_saisie = load_donnees_saisie(self.id_projet)
        self.typologie = load_typologie_data(self.donnees_saisie["typologie"])
        self.temperature_data = load_temperature_data(self.donnees_saisie["departement"])
        self.load_rendement_ecs = load_rendement_ecs(self.donnees_saisie["energie_ecs"])
        self.rendement = self.load_rendement_ecs["rendement"]
        self.slug_energi_ecs = self.donnees_saisie["energie_ecs"]
        self.Energie_ecs = SLUG_TO_TYPE_ECS.get(self.slug_energi_ecs)
        self.slug_sus_chauffage = self.donnees_saisie["systeme_chauffage"]
        self.systeme_chauffage = SLUG_TO_TYPE_ECS.get(self.slug_sus_chauffage)
        self.efficacite_chauffage = self.load_rendement_ecs["efficacite_chauffage"]
        self.rendement_production = self.load_rendement_ecs["Rendement_production"]
        self.Rendement_globale = self.load_rendement_ecs["Rendement_global"]
        self.ventilation_slug = self.donnees_saisie["ventilation"]
        self.puissance_ventilation = get_puissance_ventilation(self.ventilation_slug)
        self.annee_construction = self.donnees_saisie["annee_construction"]
        self.coef_GV_amorti, self.coef_g = load_coefficients_gv(self.annee_construction, self.ventilation_slug)
        self.slug_usage = self.donnees_saisie["usage_thermique"]
        usage_thermique = SLUG_TO_ENERGIE.get(self.slug_usage)
        self.hauteur_plafond = self.donnees_saisie["hauteur_plafond"]
        self.surface = self.donnees_saisie["surface"]
        self.surface_pv = self.donnees_saisie.get("surface_pv")
        self.prod_solaire_existante = self.donnees_saisie["prod_solaire_existante"]
        self.thermique_saisie = self.donnees_saisie["thermique_saisie"]
        self.surface_thermique = self.donnees_saisie["surface_thermique"]
        self.slug_type_toiture = self.donnees_saisie["type_toiture"]
        self.type_toiture = SLUG_TO_TOITURE.get(self.slug_type_toiture)
        self.slug_situation = self.donnees_saisie["situation"]
        self.situation = SLUG_TO_SITUATION.get(self.slug_situation)
        self.slug_zone = self.donnees_saisie["zone_administrative"]
        self.zone_administrative1 = SLUG_PATRIMOINE.get(self.slug_zone)
        self.slug_msq = self.donnees_saisie["masque"]
        self.masque = SLUG_MASQUE.get(self.slug_msq)





        self.encombrement_toiture = self.donnees_saisie["encombrement_toiture"]
        self.surface_toiture = self.donnees_saisie["surface_toiture"]
        self.surface_parking = self.donnees_saisie["surface_parking"]
        self.cons_ann_kwh = self.donnees_saisie["conso_elec_initial"]
        self.slug_strategie = self.donnees_saisie["strategie"]
        self.strategie = SLUG_TO_STRATEGIE.get(self.slug_strategie)
 #   # Taux ENR principal
        taux_enr_principal_val = self.donnees_saisie.get("taux_enr_principal")
        self.taux_enr_principal = (taux_enr_principal_val or 0) / 100

# Taux ENR appoint
        taux_enr_appoint_val = self.donnees_saisie.get("taux_enr_appoint")
        self.taux_enr_appoint = (taux_enr_appoint_val or 0) / 100



        
       

       ## les sorties de besoins_ecs40 : 
        self.typology = self.typologie["typologie"]
        self.besoins_ecs_40 = self.typologie["Besoins_ECS_40"]
        self.jours_ouvrés = self.typologie["jours_ouvrés"]
        self.heures_Fonctionnement = self.typologie["heures_fonctionnement"]
        self.debit = self.typologie["Debit_de_ventilation"]
        self.heures_F = self.typologie["Heures_fonctionnement_occupation"]
        self.modulation = self.typologie["Modulation_débit_en_occupation"]
        self.heures_f_I = self.typologie["Heures_fonctionnement_inoccupation"]
        self.reduction_debit = self.typologie["Réduction_de_débit_en_inoccupation"]
        self.Puissance_surfacique = self.typologie["W_mm"]
        self.C_USE = self.typologie["C_USE"]
        self.N_consigne_semaine = self.typologie["nombre_de_consigne_semaine"]
        self.N_reduit_semaine = self.typologie["nombre_de_reduit_semaine"]
        self.temperature_consigne = self.typologie["Temperature_de_consignes"]
        self.temperature_reduit = self.typologie["Temperature_de_reduit"]
        self.coef_reduction = self.typologie["Coeff_réduction_apports_internes_et_solaires"]

        ## sortie de temperature_froide 
        self.zone_climatique = self.temperature_data["zone_climatique"]
        self.T_exterieur_base = self.temperature_data["Text_de_base"]
        self.dju = self.temperature_data["DJU_moyen_Base_18_2000_2020"]
        self.zone = self.temperature_data["zone_ensoleillement"]
        self.temperature_retenue = self.temperature_data["temperature_moyenne"]

        

        ##les calculs :

        Consommation_ventilation  = self.debit * self.puissance_ventilation /1000 * self.heures_F * self.modulation + self.debit * self.puissance_ventilation /1000 * self.heures_f_I * self.reduction_debit
        Conso_eclairage = (self.Puissance_surfacique * self.heures_Fonctionnement)/1000
        Volume = self.hauteur_plafond * self.surface
        Deperdition_max = Volume * self.coef_GV_amorti * (self.temperature_consigne - self.T_exterieur_base)/1000
        dju_amorti = self.dju + Nombres_semaines_chauffage * 7/168 *((self.temperature_consigne - 18 ) * self.N_consigne_semaine + (self.temperature_reduit - 18 )* self.N_reduit_semaine)
        calcul_conso_chauffage = Volume * self.coef_GV_amorti / 1000 * 24 * dju_amorti * (1-(self.coef_reduction)) / (self.efficacite_chauffage) / self.surface
        Conso_specifique = (self.C_USE - Conso_eclairage)



    def _recuperer_dernier_id_projet(self) -> str:
        """Récupère le dernier id_projet inséré dans la table `input`"""
        query = text("SELECT TOP 1 id_projet FROM input ORDER BY date_creation DESC")
        with engine.connect() as conn:
            result = conn.execute(query).fetchone()
            if not result:
                raise ValueError("❌ Aucun projet trouvé dans la table 'input'")
            return result[0]
        
    

    def run(self):
        self.donnees_saisie = load_donnees_saisie(self.id_projet)


        slug_principal = self.donnees_saisie["e_t_principal"]
        slug_appoint = self.donnees_saisie["e_t_appoint"]
        reseau_principal = self.donnees_saisie.get("reseau_principal")
        reseau_appoint = self.donnees_saisie.get("reseau_appoint")
        prod_ecs_slug = self.donnees_saisie.get("type_production_ecs") 
        rendement = self.load_rendement_ecs.get("rendement")





    # 2. Mapper vers libellés
        E_T_principal = SLUG_TO_ENERGIE.get(slug_principal)
        E_T_appoint = SLUG_TO_ENERGIE.get(slug_appoint)
        type_prod_ecs = SLUG_TO_PRODUCTION_ECS.get(prod_ecs_slug)

        if not E_T_principal or not E_T_appoint:
           raise ValueError("Slug énergie inconnu (principal ou appoint)")

    # 3. Extraire les conso
        conso_principal = self.donnees_saisie["conso_principal"]
        conso_appoint = self.donnees_saisie["conso_appoint"]
        conso_elec = self.donnees_saisie["conso_elec_initial"]
        surface = self.donnees_saisie["surface"]

    # 4. Convertir les consommations
        conso_principal_1_convertie = convertir_consommation(E_T_principal, conso_principal)
        conso_principal_2_convertie = convertir_consommation(E_T_appoint, conso_appoint)

        Consommations_annuelles_totales_initiales = conso_elec + conso_principal_1_convertie + conso_principal_2_convertie 
        Consommations_annuelles_totales_initiales_ratio = Consommations_annuelles_totales_initiales / surface
        consos = [conso_principal_1_convertie ,conso_principal_2_convertie , conso_elec ]
        energis = [slug_principal , slug_appoint , "elec"]
        total_impact, total_cout = calcul_carbone_et_cout_sql(energis , consos ,reseau_principal , reseau_appoint )

        result_obj = output(
        id_projet=self.id_projet,
        conso_annuelles_totales_initiales=round(Consommations_annuelles_totales_initiales, 2),
        conso_annuelles_totales_initiales_ratio=Consommations_annuelles_totales_initiales_ratio,
        cout_total_initial=round(total_cout, 2),
        
        conso_carbone_initial=round(total_impact, 2))
        

        # Stocker dans la base output de sql server !
        with get_session() as session:
          session.add(result_obj)
          session.commit()
          session.refresh(result_obj)
        # Retourner en JSON pour l'api
        return result_obj.model_dump(exclude={"Id"})

       




        

        
