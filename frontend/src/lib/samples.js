export const medicationSample = {
  patient_context: {
    age: 67,
    conditions: ["Type 2 Diabetes", "Hypertension"],
    recent_labs: {
      eGFR: 45,
    },
  },
  sources: [
    {
      system: "Hospital EHR",
      medication: "Metformin 1000mg twice daily",
      last_updated: "2024-10-15",
      source_reliability: "high",
    },
    {
      system: "Primary Care",
      medication: "Metformin 500mg twice daily",
      last_updated: "2025-01-20",
      source_reliability: "high",
    },
    {
      system: "Pharmacy",
      medication: "Metformin 1000mg daily",
      last_filled: "2025-01-25",
      source_reliability: "medium",
    },
  ],
};

export const qualitySample = {
  demographics: {
    name: "John Doe",
    dob: "1955-03-15",
    gender: "M",
  },
  medications: ["Metformin 500mg", "Lisinopril 10mg"],
  allergies: [],
  conditions: ["Type 2 Diabetes"],
  vital_signs: {
    blood_pressure: "340/180",
    heart_rate: 72,
  },
  last_updated: "2024-06-15",
};
