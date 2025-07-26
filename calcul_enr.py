from app.moteur_calcul.loader  import load_donnees_saisie , load_rendement_ecs , get_puissance_ventilation
from app.moteur_calcul.loader  import load_typologie_data , load_temperature_data , load_coefficients_gv
from app.moteur_calcul.hypotheses.conversion import conversion
from app.moteur_calcul.conso_initial import convertir_consommation  , calcul_commun , repartition_usages , calcul_Pv , faisabilite , calcul_thermique , calcul_hybride
from app.moteur_calcul.conso_initial import calcul_carbone_et_cout_sql
from app.models.output import output  # à adapter selon ton arborescence
from app.db.database import get_session
import json
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
SLUG_ENCOMBREMENT_TOITURE = {
    "tl": "Toiture libre",
    "peu_encombre": "Peu encombrée (gaines, extracteurs…)",
    "tres_encombre": "Très encombrée (équipements techniques, gaines etc…)"
}

SLUG_MASQUE = {
    "batiment_moins_lh": "Bâtiment à moins de L=H",
    "vegetation_dense_haute": "Végétation dense et haute",
    "vegetation_peu_impactante": "Végétation peu impactante",
    "aucun": "Aucun"
}

SLUG_PATRIMOINE = {
    "so": "Sans objet",
    "bc": "Bâtiment classé",
    "abf": "Périmètre ABF / abords des monuments historiques"
}




class ProjetCalcul:
    def __init__(self , id_projet:str):
        self.id_projet = id_projet

        #self.id_projet = self._recuperer_dernier_id_projet()
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
        self.usage_thermique = SLUG_USAGE_THERMIQUE.get(self.slug_usage)
        self.hauteur_plafond = self.donnees_saisie["hauteur_plafond"]
        self.surface = self.donnees_saisie["surface"]
        self.surface_pv = self.donnees_saisie.get("surface_pv") or 0
        print("🕵️‍♀️ surface_pv =", self.surface_pv)
        print("📦 Contenu complet de donnees_saisie :", self.donnees_saisie)

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
        self.conso_elec = self.donnees_saisie["conso_elec_initial"]

        





        self.encombrement_toiture_slug = self.donnees_saisie["encombrement_toiture"]
        self.encombrement_toiture = SLUG_ENCOMBREMENT_TOITURE.get(self.encombrement_toiture_slug)


        self.surface_toiture = self.donnees_saisie["surface_toiture"]
        self.surface_parking = self.donnees_saisie["surface_parking"]
        self.cons_ann_kwh = self.donnees_saisie["conso_elec_initial"]
        self.slug_strategie = self.donnees_saisie["strategie"]
        self.strategie = SLUG_TO_STRATEGIE.get(self.slug_strategie)
     #### Vérification et récupération du taux ENR principal
        # Taux ENR principal
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
        self.pv_saisie = self.donnees_saisie.get("pv_saisie")

        ## sortie de temperature_froide 
        self.zone_climatique = self.temperature_data["zone_climatique"]
        self.T_exterieur_base = self.temperature_data["Text_de_base"]
        self.dju = self.temperature_data["DJU_moyen_Base_18_2000_2020"]
        self.zone = self.temperature_data["zone_ensoleillement"]
        self.temperature_retenue = self.temperature_data["temperature_moyenne"]

        

        


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

        ##les calculs :

        self.Consommation_ventilation  = self.debit * self.puissance_ventilation /1000 * self.heures_F * self.modulation + self.debit * self.puissance_ventilation /1000 * self.heures_f_I * self.reduction_debit
        self.Conso_eclairage = (self.Puissance_surfacique * self.heures_Fonctionnement)/1000
        self.Volume = self.hauteur_plafond * self.surface
        self.Deperdition_max = self.Volume * self.coef_GV_amorti * (self.temperature_consigne - self.T_exterieur_base)/1000
        self.dju_amorti = self.dju + Nombres_semaines_chauffage * 7/168 *((self.temperature_consigne - 18 ) * self.N_consigne_semaine + (self.temperature_reduit - 18 )* self.N_reduit_semaine)
        self.calcul_conso_chauffage = self.Volume * self.coef_GV_amorti / 1000 * 24 * self.dju_amorti * (1-(self.coef_reduction)) / (self.efficacite_chauffage) / self.surface
        self.Conso_specifique = (self.C_USE - self.Conso_eclairage)



    # 2. Mapper vers libellés
        E_T_principal = SLUG_TO_ENERGIE.get(slug_principal)
        E_T_appoint = SLUG_TO_ENERGIE.get(slug_appoint)
        self.type_prod_ecs = SLUG_TO_PRODUCTION_ECS.get(prod_ecs_slug)

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

        self.Consommations_annuelles_totales_initiales = conso_elec + conso_principal_1_convertie + conso_principal_2_convertie 
        self.Consommations_annuelles_totales_initiales_ratio = self.Consommations_annuelles_totales_initiales / surface
        consos = [conso_principal_1_convertie ,conso_principal_2_convertie , conso_elec ]
        self.energis = [slug_principal , slug_appoint , "elec"]
        self.total_impact, self.total_cout = calcul_carbone_et_cout_sql(self.energis , consos ,reseau_principal , reseau_appoint )

       
      ##  calcul_commun (self.zone , self.masque , self.surface_pv , self.prod_solaire_existante, self.pv_saisie , self.thermique_saisie , self.surface_thermique)
       # repartition_usages(self.calcul_conso_chauffage , conso_elec , self.rendement_production , self.Consommation_ventilation , self.Conso_specifique, self.Conso_eclairage,self.Consommations_annuelles_totales_initiales, self.usage_thermique,self.zone_climatique , self.surface ,  self.typology ,self.besoins_ecs_40 , self.temperature_retenue , self.type_prod_ecs , self.jours_ouvrés , self.rendement , E_T_principal , E_T_appoint , conso_principal_1_convertie , conso_principal_2_convertie , self.Energie_ecs , self.systeme_chauffage , self.zone , self.masque , self.surface_pv , self.prod_solaire_existante, self.pv_saisie , self.thermique_saisie , self.surface_thermique)
       # print(self.encombrement_toiture_slug)
        
        
        self.conso_surfacique_clim , self.total_ECS , self.besoin_60 , self.perte_bouclage , self.conso_E_ECS , self.taux_enr_initial , self.Prod_enr_bois , self.conso_elec_PAC , self.usages_energitiques1 , self.conso_energitiques1 , self.energie_PAC_delivre = repartition_usages(self.calcul_conso_chauffage , self.conso_elec , self.rendement_production , self.Consommation_ventilation , self.Conso_specifique, self.Conso_eclairage,self.Consommations_annuelles_totales_initiales, self.usage_thermique,self.zone_climatique , self.surface ,  self.typology ,self.besoins_ecs_40 , self.temperature_retenue , self.type_prod_ecs , self.jours_ouvrés , self.rendement , E_T_principal , E_T_appoint , conso_principal_1_convertie , conso_principal_2_convertie , self.Energie_ecs , self.systeme_chauffage , self.zone , self.masque , self.surface_pv , self.prod_solaire_existante, self.pv_saisie , self.thermique_saisie , self.surface_thermique)
        #print(f"les ration sont {ratio_elec}")
        print("type usages =", type(self.usages_energitiques1))
        print("type conso =", type(self.conso_energitiques1))
    

        usages_energitiques = json.dumps(self.usages_energitiques1)
        conso_energitiques = json.dumps(self.conso_energitiques1)
        print("✅ CONTROLE AVANT CALCUL_PV :")
        print("taux_enr_principal =", self.taux_enr_principal)
        print("taux_enr_appoint =", self.taux_enr_appoint)
        print("surface_pv =", self.surface_pv)
        print("surface_thermique =", self.surface_thermique)
        print("encombrement_toiture =", self.encombrement_toiture)
        print("typologie =", self.typologie)

        self.Puissance_pv_retenue  ,self.ratio_conso_totale_projet_pv ,  self.enr_local_pv , self.enr_local_max_pv , self.enr_globale , self.enr_globale_scenario_max  ,   self.total_impact_pv, self.total_cout_pv , self.conso_thermique_appoint_proj , self.surface_pv_toiture_max = calcul_Pv (self.type_toiture ,self.conso_elec , self.surface , self.energis,  self.strategie , E_T_principal , E_T_appoint , reseau_principal , reseau_appoint , self.taux_enr_principal , self.taux_enr_appoint , self.encombrement_toiture , conso_principal_1_convertie,conso_principal_2_convertie , self.surface_toiture , self.surface_parking , self.zone , self.masque ,self.systeme_chauffage , self.typologie ,  self.surface_pv , self.prod_solaire_existante, self.pv_saisie , self.thermique_saisie , self.surface_thermique , self.calcul_conso_chauffage , self.rendement_production , self.Consommation_ventilation , self.Conso_specifique, self.Conso_eclairage ,self.Consommations_annuelles_totales_initiales , self.Energie_ecs ,  self.rendement , self.jours_ouvrés ,self.besoins_ecs_40 , self.temperature_retenue , self.type_prod_ecs , self.usage_thermique, self.zone_climatique , self.typology  )  
        self.pv_resultat = [ self.Puissance_pv_retenue  ,self.ratio_conso_totale_projet_pv ,  self.enr_local_pv , self.enr_local_max_pv , self.enr_globale , self.enr_globale_scenario_max  ,   self.total_impact_pv,self.total_cout_pv , self.conso_thermique_appoint_proj , self.surface_pv_toiture_max
]
        faisabilite( self.type_toiture, self.situation, self.zone_administrative1)
        self.surface_solaire_thermique_retenue ,  self.ratio_conso_totale_proj_thermique , self.taux_ENR_Local_thermique , self.taux_ENR_Local_thermique_max , self.enr_globale_thermique , self.enr_globale_thermique_scenario_max ,  self.total_impact_thermique ,    self.total_cout_thermique =calcul_thermique (self.type_toiture , self.rendement ,conso_elec , self.strategie , E_T_principal , E_T_appoint , self.surface , self.energis , self.taux_enr_principal , self.taux_enr_appoint , reseau_principal , reseau_appoint ,  conso_principal_1_convertie , conso_principal_2_convertie   , self.zone , self.masque , self.surface_pv , self.prod_solaire_existante, self.pv_saisie , self.thermique_saisie , self.surface_thermique , self.calcul_conso_chauffage, self.rendement_production , self.Consommation_ventilation , self.Conso_specifique, self.Conso_eclairage,self.Consommations_annuelles_totales_initiales, self.Energie_ecs , self.systeme_chauffage , self.encombrement_toiture ,self.usage_thermique, self.zone_climatique , self.surface_parking ,  self.surface_toiture , self.typology ,self.besoins_ecs_40 , self.temperature_retenue , self.typologie ,  self.type_prod_ecs , self.jours_ouvrés  ) 
        self.thermique_resultat = [    self.surface_solaire_thermique_retenue ,  self.ratio_conso_totale_proj_thermique , self.taux_ENR_Local_thermique , self.taux_ENR_Local_thermique_max , self.enr_globale_thermique , self.enr_globale_thermique_scenario_max ,  self.total_impact_thermique ,    self.total_cout_thermique
]
       # print(f"les resultats sont : {thermique_resultat[2]}")
        
        self.surface_solaire_hybride_retenue , self.ratio_conso_totale_proj_hybride, self.taux_ENR_Local_hybride ,self.taux_ENR_Local_hybride_scenario_max, self.enr_globale_hybride , self.enr_globale_hybride_scenario_max   , self.conso_carbone_hybride, self.cout_total_hybride = calcul_hybride(self.type_toiture , self.rendement  , conso_elec , self.energis , self.strategie , E_T_principal , E_T_appoint ,  self.surface , self.taux_enr_principal , reseau_principal , reseau_appoint , self.taux_enr_appoint ,  conso_principal_1_convertie , conso_principal_2_convertie , self.calcul_conso_chauffage ,self.zone , self.masque , self.surface_pv , self.prod_solaire_existante, self.pv_saisie , self.thermique_saisie , self.surface_thermique ,  self.rendement_production , self.Consommation_ventilation , self.Conso_specifique, self.Conso_eclairage,self.Consommations_annuelles_totales_initiales, self.typology ,self.besoins_ecs_40 , self.encombrement_toiture, self.temperature_retenue , self.type_prod_ecs , self.jours_ouvrés ,  self.usage_thermique, self.zone_climatique , self.surface_toiture , self.surface_parking , self.typologie, self.Energie_ecs , self.systeme_chauffage ) 
        self.hybride_resultat = [   self.surface_solaire_hybride_retenue , self.ratio_conso_totale_proj_hybride, self.taux_ENR_Local_hybride ,self.taux_ENR_Local_hybride_scenario_max, self.enr_globale_hybride , self.enr_globale_hybride_scenario_max   , self.conso_carbone_hybride, self.cout_total_hybride 
]
        self.meilleur , self.details = self.choisir_meilleur_scenario_ENR(self.pv_resultat, self.thermique_resultat, self.hybride_resultat , self.type_toiture, self.situation, self.zone_administrative1)
       # print(f"les resultats de meilleur sont : {meilleur}")

        

        
        conso_json = json.dumps(self.conso_energitiques1)

    
   

       


        result_obj = output(
        id_projet=self.id_projet,
        conso_annuelles_totales_initiales=round(self.Consommations_annuelles_totales_initiales, 2),
        conso_annuelles_totales_initiales_ratio=self.Consommations_annuelles_totales_initiales_ratio,
        cout_total_initial=round(self.total_cout, 2),
        
        conso_carbone_initial=round(self.total_impact, 2),
       # usages_energitiques=usages_json,
        usages_energitiques=usages_energitiques,
        conso_energitiques= conso_energitiques , 
        enr_retenue=self.meilleur["enr_retenue"],
        puissance_retenue=self.meilleur["puissance_retenue"],
        ratio_conso_totale_projet=self.meilleur["ratio_conso_totale_projet"],
        enr_local=self.meilleur["enr_local"],
        enr_local_max=self.meilleur["enr_local_max"],
        enr_global=self.meilleur["enr_globale"],
        enr_globale_scenario_max=self.meilleur["enr_globale_scenario_max"],
        conso_carbone_pv=self.meilleur["conso_carbone_pv"],
        cout_total_pv=self.meilleur["cout_total_pv"],
        lettre_faisabilite=self.meilleur["lettre_faisabilite"])
        #usages_energitiques = usages_energitiques1 ,
        #conso_energitiques = conso_energitiques1)
        #usages_energitiques=json.dumps(usages_energitiques1),
        #conso_energitiques=json.dumps(conso_energitiques1))

        

        # Stocker dans la base output de sql server !
        with get_session() as session:
          session.add(result_obj)
          session.commit()
          session.refresh(result_obj)
        # Retourner en JSON pour l'api
        return result_obj.model_dump(exclude={"Id"})

       


    def choisir_meilleur_scenario_ENR(self, pv_resultat, thermique_resultat, hybride_resultat , type_toiture, situation,zone_administrative1):
     lettre  , details_impacts=      faisabilite( type_toiture, situation, zone_administrative1)

    
     enr_local_pv = pv_resultat[1]               # 2ème élément
     taux_enr_thermique = thermique_resultat[2]  # 3ème élément
     taux_enr_hybride = hybride_resultat[4]      # 5ème élément

     scenarios = [
        ("PV", pv_resultat[2], pv_resultat),             # enr_local_pv
        ("Thermique", thermique_resultat[2], thermique_resultat),  # taux_ENR_Local_thermique
        ("Hybride", hybride_resultat[2], hybride_resultat)         # taux_ENR_Local_hybride
    ]

     meilleur = max(scenarios, key=lambda x: x[1])  # x[1] = taux ENR
     nom, taux, result = meilleur

    # 3. Mapper dynamiquement le résultat
     if nom == "PV":
        data = {
            "puissance_retenue": result[0],
            "ratio_conso_totale_projet": result[1],
            "enr_local": result[2],
            "enr_local_max": result[3],
            "enr_globale": result[4],
            "enr_globale_scenario_max": result[5],
            "conso_carbone_pv": result[6],
            "cout_total_pv": result[7],
            "lettre_faisabilite": lettre,
        }
     elif nom == "Thermique":
        data = {
            "puissance_retenue": result[0],
            "ratio_conso_totale_projet": result[1],
            "enr_local": result[2],
            "enr_local_max": result[3],
            "enr_globale": result[4],
            "enr_globale_scenario_max": result[5],
            "conso_carbone_pv": result[6],
            "cout_total_pv": result[7],
            "lettre_faisabilite": lettre,
        }
     else:  # Hybride
        data = {
            "puissance_retenue": result[0],
            "ratio_conso_totale_projet": result[1],
            "enr_local": result[2],
            "enr_local_max": result[3],
            "enr_globale": result[4],
            "enr_globale_scenario_max": result[5],
            "conso_carbone_pv": result[6],
            "cout_total_pv": result[7],
            "lettre_faisabilite": lettre,
        }

    # 4. Ajouter les infos globales
     data.update({
        "enr_retenue": nom,
        })

     print(f"✅ Meilleur scénario : {nom} avec {round(taux, 2)}% EnR locaux")
     return data , details_impacts