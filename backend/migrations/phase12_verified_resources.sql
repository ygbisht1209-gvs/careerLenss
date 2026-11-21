insert into public.learning_categories (slug, name)
values
    ('programming', 'Programming'),
    ('web-development', 'Web development'),
    ('databases', 'Databases'),
    ('developer-tools', 'Developer tools'),
    ('testing', 'Testing')
on conflict (slug) do update
set name = excluded.name;

insert into public.learning_resources (
    category_slug,
    title,
    description,
    provider,
    resource_url,
    difficulty,
    resource_type,
    skill_tags,
    objectives,
    is_active
)
select
    category_slug,
    title,
    description,
    provider,
    resource_url,
    difficulty,
    resource_type,
    skill_tags,
    objectives,
    true
from (
    values
        ('programming', 'The Python Tutorial', 'Learn Python syntax, data structures, functions, modules, input/output, and standard-library basics from the language maintainers.', 'Python Software Foundation', 'https://docs.python.org/3/tutorial/', 'Beginner', 'documentation', array['Python'], array['Understand core Python syntax', 'Practice functions and data structures']),
        ('programming', 'JavaScript Guide', 'Review JavaScript fundamentals and language features using Mozilla''s maintained reference and guide.', 'MDN Web Docs', 'https://developer.mozilla.org/en-US/docs/Web/JavaScript', 'All levels', 'documentation', array['JavaScript', 'Node.js'], array['Understand JavaScript language features', 'Use JavaScript in browser and server contexts']),
        ('web-development', 'Structuring content with HTML', 'Learn semantic HTML structure, elements, attributes, and accessible page foundations.', 'MDN Web Docs', 'https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Structuring_content', 'Beginner', 'tutorial', array['HTML', 'Communication'], array['Create semantic HTML', 'Understand accessible document structure']),
        ('web-development', 'Learn CSS', 'Study CSS fundamentals, layout, responsive design, selectors, and browser rendering.', 'MDN Web Docs', 'https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Styling_basics', 'Beginner', 'tutorial', array['CSS', 'HTML'], array['Style semantic pages', 'Build responsive layouts']),
        ('web-development', 'Quick Start', 'Learn the core React concepts with the official examples and interactive learning guide.', 'React', 'https://react.dev/learn', 'Beginner', 'documentation', array['React', 'JavaScript'], array['Create components', 'Manage state and props', 'Render UI from data']),
        ('web-development', 'Flask Quickstart', 'Build a small Flask application, routes, request handling, templates, and basic responses.', 'Pallets', 'https://flask.palletsprojects.com/en/stable/quickstart/', 'Beginner', 'documentation', array['Flask', 'Python', 'REST APIs'], array['Create Flask routes', 'Handle requests and responses', 'Validate basic input']),
        ('databases', 'SQL Tutorial', 'Practice relational database concepts and SQL queries step by step with small exercises.', 'SQLZoo', 'https://sqlzoo.net/wiki/SQL_Tutorial', 'Beginner', 'practice', array['SQL'], array['Use filtering and joins', 'Practice aggregation and subqueries']),
        ('databases', 'PostgreSQL Tutorial', 'Follow the official PostgreSQL tutorial covering tables, queries, joins, aggregates, and transactions.', 'PostgreSQL Global Development Group', 'https://www.postgresql.org/docs/current/tutorial.html', 'Beginner', 'documentation', array['PostgreSQL', 'SQL'], array['Create a relational schema', 'Write basic and advanced queries']),
        ('developer-tools', 'Git Tutorials', 'Learn version control concepts, commits, branching, merge workflows, and collaboration with Git.', 'GitLab', 'https://docs.gitlab.com/tutorials/learn_git/', 'Beginner', 'tutorial', array['Git'], array['Create commits', 'Use branches', 'Resolve merge conflicts']),
        ('developer-tools', 'Learn Docker by doing', 'Learn how to build, run, and share containerized applications using Docker.', 'Docker', 'https://docs.docker.com/learn/', 'Beginner', 'tutorial', array['Docker', 'Linux'], array['Build an application image', 'Run containers', 'Publish a container']),
        ('testing', 'Pytest Getting Started', 'Learn how to write and run tests for Python applications with pytest fixtures and assertions.', 'pytest', 'https://docs.pytest.org/en/stable/getting-started.html', 'Beginner', 'documentation', array['Testing', 'Pytest', 'Python'], array['Write unit tests', 'Exercise success and failure cases', 'Run test suites']),
        ('testing', 'Testing JavaScript', 'Explore practical JavaScript testing concepts and tools documented in the Jest ecosystem.', 'Jest', 'https://jestjs.io/docs/getting-started', 'Beginner', 'documentation', array['Testing', 'JavaScript'], array['Write behavior-focused tests', 'Test success and failure states', 'Run JavaScript test suites'])
) as seed(
    category_slug,
    title,
    description,
    provider,
    resource_url,
    difficulty,
    resource_type,
    skill_tags,
    objectives
)
where not exists (
    select 1
    from public.learning_resources existing
    where existing.resource_url = seed.resource_url
);

notify pgrst, 'reload schema';
