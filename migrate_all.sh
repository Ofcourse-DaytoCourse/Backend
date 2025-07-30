#!/bin/bash

NEON_URL='postgresql://neondb_owner:npg_nYlf1eLv7PHJ@ep-quiet-field-a1pfu8j2-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

echo "🚀 Starting migration..."

cd /Users/hwangjunho/Desktop/back/Backend

echo "1. Creating base schema..."
psql "$NEON_URL" -f create_database_postgresql.sql

echo "2. Running migrations..."
cd migrations

echo "  - Adding foreign key constraints..."
psql "$NEON_URL" -f add_foreign_key_constraints.sql -q

echo "  - Adding place category relations..."
psql "$NEON_URL" -f add_place_category_relations.sql -q

echo "  - Adding payment system tables..."
psql "$NEON_URL" -f add_payment_system_tables.sql -q

echo "  - Adding place reviews table..."
psql "$NEON_URL" -f add_place_reviews_table.sql -q

echo "  - Adding new place columns..."
psql "$NEON_URL" -f add_new_place_columns.sql -q

echo "  - Adding soft delete for courses..."
psql "$NEON_URL" -f add_soft_delete_courses.sql -q

echo "  - Creating shared course tables..."
psql "$NEON_URL" -f create_shared_course_tables_fixed.sql -q

echo "  - Adding refund service type..."
psql "$NEON_URL" -f add_refund_service_type.sql -q

echo "  - Refactoring refund system..."
psql "$NEON_URL" -f refactor_refund_system.sql -q

echo "  - Adding AI search service type..."
psql "$NEON_URL" -f add_ai_search_service_type.sql -q

echo "  - Adding shared courses only..."
psql "$NEON_URL" -f shared_courses_only.sql -q

echo "3. Loading place data..."
cd ..
python load_places_data_postgres.py

echo "✅ Migration complete!"
echo "🎯 Database ready at: $NEON_URL"