-- NutriLenz MySQL schema. Run by MySQLDataStore.initialise(); safe to run again.

CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(40) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    avoid_ingredients JSON NOT NULL,
    dietary_checks JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goals (
    goal_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    nutrient VARCHAR(30) NOT NULL,
    direction ENUM('MAX', 'MIN') NOT NULL,
    target DECIMAL(10, 2) NOT NULL,
    UNIQUE KEY one_goal_per_nutrient (user_id, nutrient),
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    product_name VARCHAR(120) NOT NULL,
    brand VARCHAR(80) NULL,
    category VARCHAR(60) NULL,
    nutrition JSON NOT NULL,
    ingredient_text TEXT NOT NULL,
    marketing_claim VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analyses (
    analysis_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    product_id INT NOT NULL,
    profile_snapshot JSON NOT NULL,
    ai_analysis JSON NOT NULL,
    goal_results JSON NOT NULL,
    dietary_results JSON NULL,
    flags JSON NOT NULL,
    score DECIMAL(5, 1) NOT NULL,
    provider VARCHAR(20) NOT NULL,
    analysed_at DATETIME NOT NULL,
    INDEX user_history (user_id, analysed_at),
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products (product_id) ON DELETE RESTRICT
);
