// scripts/mongo-init.js
// MongoDB initialisation — runs on first container start
// Creates DB, collections, and indexes for IntelliHire Module 1

db = db.getSiblingDB("intellihire");

// ── Create collections with schema validation ─────────────

db.createCollection("resumes", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["name", "email", "uploaded_at"],
      properties: {
        name:          { bsonType: "string" },
        email:         { bsonType: "string" },
        uploaded_at:   { bsonType: "date" },
        file_type:     { enum: ["pdf", "docx", "generated"] },
        word_count:    { bsonType: "int", minimum: 0 },
      },
    },
  },
  validationAction: "warn",   // warn only (not block) in dev
});

db.createCollection("analyses");
db.createCollection("job_descriptions");

// ── Indexes ───────────────────────────────────────────────

// resumes: lookup by email, sort by upload date
db.resumes.createIndex({ email: 1 });
db.resumes.createIndex({ uploaded_at: -1 });

// analyses: lookup by resume_id (most common query pattern)
db.analyses.createIndex({ resume_id: 1 });
db.analyses.createIndex({ analyzed_at: -1 });

// job_descriptions: sort by recency
db.job_descriptions.createIndex({ created_at: -1 });

print("✅ IntelliHire MongoDB initialised — collections and indexes created.");
