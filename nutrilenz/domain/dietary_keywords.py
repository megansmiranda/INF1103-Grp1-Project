class DietaryKeywords:
    """Words transcribed from the supplied images, plus the existing allergens.

    The images list 42 vegetarian terms and 26 vegan additions (68 total).
    """

    GROUPS = {
        "meat": ("beef", "pork", "chicken", "duck", "lamb", "mutton", "turkey",
                 "bacon", "ham", "meat"),
        "animal_fats": ("lard", "tallow", "suet"),
        "fish": ("fish", "tuna", "salmon", "sardine", "mackerel", "anchovy",
                 "anchovies", "fish sauce", "oyster sauce"),
        "shellfish": ("prawn", "shrimp", "crab", "lobster", "crayfish", "krill",
                      "oyster", "mussel", "clam", "scallop", "squid", "cuttlefish", "octopus"),
        "hidden_animal": ("gelatine", "gelatin", "collagen", "isinglass", "rennet",
                          "carmine", "cochineal"),
        "dairy": ("milk", "milk powder", "dairy", "whey", "casein", "caseinate", "lactose",
                  "butter", "buttermilk", "cream", "cheese", "yoghurt", "yogurt", "ghee", "curd"),
        "egg": ("egg", "egg white", "egg yolk", "albumen", "albumin", "mayonnaise", "meringue"),
        "other_animal": ("honey", "beeswax", "shellac", "royal jelly"),
        "halal_pork": ("pork", "lard", "bacon", "ham", "pancetta"),
        "halal_gelatine": ("gelatine", "gelatin"),
        "alcohol": ("alcohol", "ethanol", "wine", "rum", "beer", "brandy", "liqueur", "mirin", "sake"),
        "nuts": ("nut", "peanut", "almond", "cashew", "walnut", "hazelnut", "pistachio",
                 "pecan", "macadamia", "brazil nut", "pine nut"),
        "gluten": ("gluten", "wheat", "barley", "rye", "malt", "spelt", "semolina"),
        "soy": ("soy", "soya", "soybean", "tofu", "tempeh", "edamame"),
    }
    EXCEPTIONS = {
        "dairy": ("coconut milk", "coconut cream", "coconut butter", "almond milk",
                  "soy milk", "soya milk", "oat milk", "rice milk", "cashew milk",
                  "peanut butter", "almond butter", "cashew butter", "cocoa butter", "shea butter"),
    }
