export const fallbackServices = [
  {
    name: "Oral Prophylaxis",
    description: "Routine cleaning and plaque removal for healthier gums.",
  },
  {
    name: "Tooth Filling",
    description: "Restorative filling treatment for cavities and minor tooth damage.",
  },
  {
    name: "Tooth Extraction",
    description: "Assessment and safe tooth removal when needed.",
  },
  {
    name: "Fluoride Treatment",
    description: "Preventive fluoride care for stronger tooth enamel.",
  },
  {
    name: "Pit & Fissure Sealant",
    description: "Protective sealant treatment for cavity-prone grooves in the teeth.",
  },
  {
    name: "Teeth Whitening",
    description: "Cosmetic whitening options for a brighter smile.",
  },
  {
    name: "Root Canal Therapy",
    description: "Treatment for infected pulp while preserving the natural tooth.",
  },
  {
    name: "Odontectomy (Wisdom Tooth Removal)",
    description: "Surgical assessment and removal of an impacted wisdom tooth.",
  },
  {
    name: "Apicoectomy",
    description: "Surgical treatment of infection around the tip of a tooth root.",
  },
  {
    name: "Gingivectomy / Gingivoplasty (Crown Lengthening)",
    description: "Gum contouring or crown-lengthening treatment for oral health and restoration.",
  },
  {
    name: "Traditional Metal Braces",
    description: "Conventional orthodontic braces for guided tooth alignment.",
  },
  {
    name: "Ceramic Braces",
    description: "Ceramic orthodontic braces for discreet tooth alignment.",
  },
  {
    name: "Sapphire Braces",
    description: "Sapphire orthodontic braces for discreet tooth alignment.",
  },
  {
    name: "Self-Ligating Braces",
    description: "Self-ligating orthodontic braces for guided tooth alignment.",
  },
  {
    name: "Invisible / Clear Aligners",
    description: "Clear removable aligners for discreet tooth alignment.",
  },
  {
    name: "Removable Partial Dentures",
    description: "Removable replacement teeth planned for fit and comfort.",
  },
  {
    name: "Direct and Indirect Veneers",
    description: "Veneer options planned to improve tooth shape and appearance.",
  },
  {
    name: "Fixed Bridge / Jacket Crowns",
    description: "Fixed restorations for missing, damaged, or weakened teeth.",
  },
  {
    name: "Retainers (Hawley / Invisible)",
    description: "Hawley or clear retainers for maintaining tooth alignment.",
  },
  {
    name: "Denture Repair / Reline / Rebase",
    description: "Denture adjustment and repair for renewed fit and comfort.",
  },
  {
    name: "Space Maintainers / Expanders",
    description: "Orthodontic appliances used to preserve or create space.",
  },
];

export const dentalServiceCategories = fallbackServices.map((service) => service.name);

function defaultServiceModalContent(serviceName = "") {
  const name = serviceName.toLowerCase();

  if (
    name.includes("brace") ||
    name.includes("orthodont") ||
    name.includes("aligner") ||
    name.includes("retainer") ||
    name.includes("space maintainer") ||
    name.includes("expander")
  ) {
    return {
      tagline: "Start your journey toward a straighter, healthier smile.",
      includes: [
        "Review of your teeth and bite alignment",
        "Discussion of suitable orthodontic options",
        "Personalized treatment recommendations",
        "Answers to your questions before treatment",
      ],
    };
  }

  if (name.includes("extract") || name.includes("odontectomy")) {
    return {
      tagline: "Understand every step of a carefully planned tooth removal.",
      includes: [
        "Assessment of the affected tooth",
        "Review of imaging when clinically needed",
        "Explanation of the treatment process",
        "Aftercare and recovery guidance",
      ],
    };
  }

  if (name.includes("prophylaxis") || name.includes("clean")) {
    return {
      tagline: "Keep your teeth clean and your gums feeling healthy.",
      includes: [
        "Initial oral health review",
        "Plaque and tartar removal",
        "Professional tooth polishing",
        "Personalized home-care guidance",
      ],
    };
  }

  if (name.includes("root canal") || name.includes("apicoectomy")) {
    return {
      tagline: "Relieve discomfort while helping preserve the natural tooth.",
      includes: [
        "Review of symptoms and dental history",
        "Diagnostic assessment and imaging if needed",
        "Explanation of the treatment stages",
        "Recovery and follow-up guidance",
      ],
    };
  }

  if (name.includes("whitening")) {
    return {
      tagline: "Explore a brighter smile with a dentist-guided plan.",
      includes: [
        "Current shade and smile assessment",
        "Suitability and sensitivity review",
        "Discussion of whitening options",
        "Maintenance and aftercare guidance",
      ],
    };
  }

  if (
    name.includes("filling") ||
    name.includes("restoration") ||
    name.includes("veneer") ||
    name.includes("sealant") ||
    name.includes("fluoride") ||
    name.includes("gingiv")
  ) {
    return {
      tagline: "Protect and restore your smile with a personalized care plan.",
      includes: [
        "Assessment of the tooth and surrounding area",
        "Discussion of suitable treatment options",
        "Explanation of materials and expected care",
        "Prevention and follow-up guidance",
      ],
    };
  }

  if (
    name.includes("crown") ||
    name.includes("bridge") ||
    name.includes("denture") ||
    name.includes("veneer")
  ) {
    return {
      tagline: "Restore comfort and function with carefully planned dental care.",
      includes: [
        "Evaluation of teeth, gums, and bite",
        "Discussion of restoration options",
        "Planning for fit, comfort, and appearance",
        "Care and maintenance guidance",
      ],
    };
  }

  return {
    tagline: "Get clear guidance for your dental care needs.",
    includes: [
      "Review of your dental concern and goals",
      "Clinical assessment by the clinic dentist",
      "Explanation of recommended next steps",
      "Time to ask questions before treatment",
    ],
  };
}

export function getServiceModalContent(service = {}) {
  const defaults = defaultServiceModalContent(service.name || "");
  const storedItems = Array.isArray(service.detail_items)
    ? service.detail_items
    : String(service.detail_items || "").split(/\r?\n/);
  const includes = storedItems.map((item) => String(item).trim()).filter(Boolean);

  return {
    tagline: String(service.detail_tagline || "").trim() || defaults.tagline,
    includes: includes.length ? includes : defaults.includes,
    duration: String(service.detail_duration || "").trim() || "By appointment",
    audience: String(service.detail_audience || "").trim() || "Individual care",
    careNote: String(service.detail_care_note || "").trim() || "Clear guidance",
  };
}

export const fallbackPromos = [
  {
    title: "New Patient Starter",
    description: "Free dental assessment with your first cleaning appointment.",
  },
  {
    title: "Family Smile Day",
    description: "Save 15% when three or more family members book checkups.",
  },
  {
    title: "Whitening Bundle",
    description: "Consultation plus whitening plan at a reduced package rate.",
  },
];
