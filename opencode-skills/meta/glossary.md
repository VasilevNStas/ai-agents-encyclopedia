# Glossary

| Термин | Определение |
|--------|-------------|
| Skill | Директория с файлом SKILL.md, содержащим инструкции для AI-агента |
| SKILL.md | Файл с YAML frontmatter (name, description) и Markdown-инструкциями |
| YAML frontmatter | Блок `---` в начале SKILL.md с метаданными (name, description, и т.д.) |
| name | Обязательное поле frontmatter. kebab-case, совпадает с именем директории |
| description | Обязательное поле frontmatter. До 1024 символов. Условия триггера skill |
| Hard Gates | Обязательные поля SKILL.md, блокирующие загрузку при отсутствии |
| Hidden Skill | Skill без description (не триггерится, доступен только через skill()) |
| Skill Tool | Механизм загрузки skill в контекст агента (вызов по имени) |
| skills-ref | CLI-утилита для валидации и отладки skills |
| Progressive disclosure | Поэтапная загрузка: метаданные → инструкции → ресурсы |
| Автотриггеринг | Агент сам решает, когда применить skill, на основе description |
| Trigger Quality | Точность, с которой skill срабатывает на релевантные запросы |
| Порог 1% | Правило: загружать skill даже при 1% вероятности совпадения |
| Superpowers | npm-пакет со стандартной библиотекой skills от Obra |
| Fleet | Парк skills, которыми управляет организация |
| Retirement | Удаление устаревших skills из парка |
| Skill chaining | Один skill направляет агента к другому через инструкцию |
| Skill Composition | Объединение нескольких skills для комплексной задачи |
| SUBAGENT-STOP | Инструкция, запрещающая subagent'ам загружать данный skill |
| Tool Mapping | Адаптация имён инструментов под конкретный CLI (OpenCode, Claude Code и т.д.) |
| Cross-agent Portability | Способность skill работать в разных AI-агентах |
| CSO | Claude Search Optimization — оптимизация description для точного триггеринга |
| Eval-запросы | Набор тестовых запросов для проверки триггеринга skill (цель: 90%+) |
| Eval-driven | Подход к тестированию skills через eval-наборы |
| Baseline | Эталонный результат, с которым сравниваются тесты |
| Property-based Testing | Тестирование на случайных входных данных с проверкой инвариантов |
| Context Window | Ограниченное пространство контекста, которое skills занимают при загрузке |
| Token ROI | Отношение пользы от skill к стоимости его токенов |
| Skill Budgeting | Лимит токенов на загрузку skills |
| Artifact | Файл, создаваемый skill-ом (документ, изображение, код) |
| Gotchas | Секция в skill с неочевидными подводными камнями |
