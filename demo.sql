CREATE TABLE students (id INT PRIMARY KEY, name TEXT, cgpa REAL, dept TEXT);
INSERT INTO students VALUES (101,'Rahim',3.4,'CSE'),(102,'Nusrat',3.8,'CSE'),(103,'Tanvir',3.1,'EEE'),(104,'Mim',3.9,'BBA');
SELECT * FROM students WHERE cgpa >= 3.4 ORDER BY cgpa DESC;
SELECT name FROM students WHERE id = 103;
EXPLAIN SELECT * FROM students WHERE id > 101 AND id <= 103;
UPDATE students SET cgpa = 3.5 WHERE id = 101;
DELETE FROM students WHERE dept = 'BBA';
SELECT COUNT(*) FROM students;
SHOW TABLES;
