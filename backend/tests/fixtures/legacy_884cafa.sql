-- Baza utworzona wersja 884cafa (initial alpha release): 2 kolacje, waga, pusty dzien, zamkniety dzien.
BEGIN TRANSACTION;
CREATE TABLE app_meta (
	"key" VARCHAR(64) NOT NULL, 
	value VARCHAR(256) NOT NULL, 
	PRIMARY KEY ("key")
);
INSERT INTO "app_meta" VALUES('default_user_bootstrapped','1');
CREATE TABLE day_entries (
	id INTEGER NOT NULL, 
	day_log_id INTEGER NOT NULL, 
	entry_order INTEGER NOT NULL, 
	entry_type VARCHAR(32) NOT NULL, 
	entry_label VARCHAR(64) NOT NULL, 
	source_text TEXT NOT NULL, 
	kcal FLOAT, 
	carbs_g FLOAT, 
	fat_g FLOAT, 
	protein_g FLOAT, 
	weight_kg FLOAT, 
	waist_cm FLOAT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(day_log_id) REFERENCES day_logs (id) ON DELETE CASCADE
);
INSERT INTO "day_entries" VALUES(1,2,1,'dinner','Kolacja','Data: 2026-09-01
Kolacja
Ilosc kalorii: 400
Weglowodany: 1
Tluszcze: 1
Bialko: 1',400.0,1.0,1.0,1.0,NULL,NULL,'2026-09-30 13:04:39.347097','2026-09-30 13:04:39.347101');
INSERT INTO "day_entries" VALUES(2,2,2,'dinner','Kolacja Drugie','Data: 2026-09-01
Kolacja
Ilosc kalorii: 300
Weglowodany: 1
Tluszcze: 1
Bialko: 1',300.0,1.0,1.0,1.0,NULL,NULL,'2026-09-30 13:04:39.375302','2026-09-30 13:04:39.376293');
INSERT INTO "day_entries" VALUES(3,3,1,'weight','Waga','Data: 2026-09-02
Waga: 88',NULL,NULL,NULL,NULL,88.0,NULL,'2026-09-30 13:04:39.402374','2026-09-30 13:04:39.402378');
CREATE TABLE day_logs (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	log_date DATE NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	daily_kcal_target_snapshot FLOAT NOT NULL, 
	total_kcal FLOAT NOT NULL, 
	total_carbs_g FLOAT NOT NULL, 
	total_fat_g FLOAT NOT NULL, 
	total_protein_g FLOAT NOT NULL, 
	balance_mode BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	closed_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_day_logs_user_date UNIQUE (user_id, log_date), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
INSERT INTO "day_logs" VALUES(1,1,'2026-09-30','open',2400.0,0.0,0.0,0.0,0.0,0,'2026-09-30 13:04:39.336746',NULL);
INSERT INTO "day_logs" VALUES(2,1,'2026-09-01','closed',2400.0,700.0,2.0,2.0,2.0,0,'2026-09-30 13:04:39.344721','2026-09-30 13:04:39.451120');
INSERT INTO "day_logs" VALUES(3,1,'2026-09-02','open',2400.0,0.0,0.0,0.0,0.0,0,'2026-09-30 13:04:39.400602',NULL);
INSERT INTO "day_logs" VALUES(4,1,'2026-09-03','open',2400.0,0.0,0.0,0.0,0.0,0,'2026-09-30 13:04:39.427300',NULL);
CREATE TABLE profiles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	sex VARCHAR(16) NOT NULL, 
	age INTEGER NOT NULL, 
	height_cm FLOAT NOT NULL, 
	weight_kg FLOAT NOT NULL, 
	activity_level VARCHAR(32) NOT NULL, 
	goal_type VARCHAR(16) NOT NULL, 
	goal_delta_pct FLOAT NOT NULL, 
	daily_kcal_target FLOAT NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_profiles_user_id UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
INSERT INTO "profiles" VALUES(1,1,'male',30,175.0,80.0,'moderate','maintain',0.0,2400.0,'2026-09-30 13:04:39');
CREATE TABLE users (
	id INTEGER NOT NULL, 
	slug VARCHAR(64) NOT NULL, 
	display_name VARCHAR(128) NOT NULL, 
	pin_hash VARCHAR(256) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
INSERT INTO "users" VALUES(1,'domyslny-uzytkownik','Domyslny Uzytkownik','90cd3183b8c035de0be956450d1f85b2:fe46b867f8fce2cab8f5cb0ac2073ee7322241d42fe92b7e15478826f2f4c210',1,'2026-09-30 13:04:39');
CREATE INDEX ix_users_id ON users (id);
CREATE UNIQUE INDEX ix_users_slug ON users (slug);
CREATE INDEX ix_profiles_user_id ON profiles (user_id);
CREATE INDEX ix_day_logs_log_date ON day_logs (log_date);
CREATE INDEX ix_day_logs_user_id ON day_logs (user_id);
CREATE INDEX ix_day_entries_day_log_id ON day_entries (day_log_id);
CREATE INDEX ix_day_entries_entry_type ON day_entries (entry_type);
COMMIT;
