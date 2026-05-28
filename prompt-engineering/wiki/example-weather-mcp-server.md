---
title: Пример MCP-сервера погоды
module: 6
type: example
tags: [mcp, server, example, weather]
author: AI-Professor
---

# Пример: MCP-сервер погоды

> Практическая реализация MCP-сервера — 30 строк кода.
> См. Модуль 6 и [[function-calling.skill.md]].

---

## Структура

```
examples/weather-mcp-server/
├── package.json      — зависимости (MCP SDK + zod)
├── index.js          — сервер (30 строк)
└── node_modules/     — установлено
```

## Код сервера

```javascript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "weather-mcp-server",
  version: "1.0.0",
});

const weatherData = {
  "Москва":    { temp: 15, condition: "облачно",   humidity: 60 },
  "Токио":     { temp: 22, condition: "солнечно",  humidity: 45 },
  "Лондон":    { temp: 12, condition: "дождь",     humidity: 80 },
};

server.tool(
  "get_weather",
  "Получить текущую погоду в городе",
  { city: z.string().describe("Название города") },
  async ({ city }) => {
    const weather = weatherData[city];
    if (!weather) {
      return { content: [{ type: "text", text: "Нет данных" }] };
    }
    return { content: [{ type: "text", text: JSON.stringify({ city, ...weather }) }] };
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
```

## Архитектура

```
OpenCode (Host)
    │
    ├── встроенные инструменты (glob, grep, read, write)
    │
    └── MCP-серверы (через opencode.json)
         │
         ├── filesystem — читает файлы проекта
         └── weather — get_weather (учебный)
```

## Как добавить свой MCP-сервер

В `opencode.json` (глобальный или в `.opencode.json` проекта):

```json
{
  "mcp": {
    "weather": {
      "type": "local",
      "command": ["node", "/путь/к/server.js"]
    }
  }
}
```

## Где искать MCP-серверы

- `npm search @modelcontextprotocol/server-*`
- `github.com/modelcontextprotocol/servers`
- `github.com/topics/mcp-server`

## Ссылки

- [[../06-mcp/06-mcp|Модуль 6: MCP]]
- [[function-calling.skill.md|Skill: Function Calling]]
