"use strict";

const tg = window.Telegram ? window.Telegram.WebApp : null;

const TEXTS = {
  kk: {
    tabs: { grades: "Бағалар", schedule: "Кесте", changes: "Өзгерістер", notes: "Жазбалар" },
    updated: "Жаңартылды",
    average: "Орташа балл",
    subjects: "Пән",
    absences: "Қатыспаған",
    avgShort: "орташа",
    week: "апта",
    weekTitle: (week) => `${week}-апта`,
    types: { L: "Дәріс", Lab: "Зертхана", SRO: "СӨЖ", Pr: "Практика" },
    absent: "н.п.",
    absentLegend: "н.п. — қатыспады",
    absencesChip: (count) => `${count} н.п.`,
    lowChip: "Төмен балл",
    byWeek: "Апталар бойынша",
    totals: "Қорытынды бағандар",
    allSubjects: "Пәндер",
    noGrades: "Журнал әлі жоқ.\nБотқа /connect, содан кейін /grades жіберіңіз.",
    noChanges: "Соңғы 30 күнде өзгеріс болған жоқ.",
    noNotes: "Жазба жоқ.\nБотқа «… есте сақта» деп жазыңыз.",
    kinds: { new: "Жаңа баға", updated: "Өзгерді", removed: "Өшірілді" },
    today: "Бүгін",
    yesterday: "Кеше",
    reminder: "Еске салу",
    openLink: "Сілтемені ашу",
    loadError: "Деректерді жүктеу мүмкін болмады. Кейінірек қайталаңыз.",
    openInTelegram: "Бұл бетті Telegram-дағы бот арқылы ашыңыз.",
    weekdaysShort: ["Дс", "Сс", "Ср", "Бс", "Жм", "Сн", "Жс"],
    weekdays: ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"],
    noSchedule: "Кесте әлі жүктелмеген.\nБотқа /schedule жіберіңіз.",
    noLessons: "Бұл күні сабақ жоқ 🎉",
    online: "Онлайн",
    join: "Teams-ке қосылу",
    room: (room) => `${room} ауд.`,
    semesterWeek: (week) => `${week}-апта`,
    todayMark: "бүгін",
  },
  ru: {
    tabs: { grades: "Оценки", schedule: "Пары", changes: "Изменения", notes: "Заметки" },
    updated: "Обновлено",
    average: "Средний балл",
    subjects: "Предметов",
    absences: "Пропусков",
    avgShort: "среднее",
    week: "неделя",
    weekTitle: (week) => `${week}-я неделя`,
    types: { L: "Лекция", Lab: "Лабораторная", SRO: "СРО", Pr: "Практика" },
    absent: "н.п.",
    absentLegend: "н.п. — пропуск",
    absencesChip: (count) => `${count} н.п.`,
    lowChip: "Низкий балл",
    byWeek: "По неделям",
    totals: "Итоговые столбцы",
    allSubjects: "Предметы",
    noGrades: "Журнала пока нет.\nОтправь боту /connect, затем /grades.",
    noChanges: "За последние 30 дней изменений не было.",
    noNotes: "Заметок нет.\nНапиши боту «запомни …».",
    kinds: { new: "Новая оценка", updated: "Изменена", removed: "Удалена" },
    today: "Сегодня",
    yesterday: "Вчера",
    reminder: "Напоминание",
    openLink: "Открыть ссылку",
    loadError: "Не удалось загрузить данные. Попробуй позже.",
    openInTelegram: "Открой эту страницу через бота в Telegram.",
    weekdaysShort: ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    weekdays: ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
    noSchedule: "Расписание ещё не загружено.\nОтправь боту /schedule.",
    noLessons: "В этот день пар нет 🎉",
    online: "Онлайн",
    join: "Подключиться в Teams",
    room: (room) => `ауд. ${room}`,
    semesterWeek: (week) => `${week}-я неделя`,
    todayMark: "сегодня",
  },
};

const TYPE_ORDER = ["L", "Lab", "SRO"];
const MARKERS = { L: "circle", Lab: "square", SRO: "triangle" };
const KIND_ICONS = { new: "🆕", updated: "🔄", removed: "➖" };

const state = { data: null, tab: "grades", subject: null, day: null };
let t = TEXTS.kk;

// ---------- Помощники ----------

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

const SVG_NS = "http://www.w3.org/2000/svg";

function svg(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function seriesColor(type) {
  return cssVar(`--series-${MARKERS[type] ? type : "other"}`);
}

function typeLabel(type) {
  return t.types[type] || type;
}

function formatNumber(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, "");
}

// Свои названия месяцев: браузеры не везде знают казахские.
const MONTHS = {
  kk: ["қаң", "ақп", "нау", "сәу", "мам", "мау", "шіл", "там", "қыр", "қаз", "қар", "жел"],
  ru: ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"],
};

function formatDate(iso, withTime = true) {
  if (!iso) return "";
  const date = new Date(iso);
  const months = MONTHS[state.data ? state.data.language : "kk"] || MONTHS.kk;
  const day = `${date.getDate()} ${months[date.getMonth()]}`;
  if (!withTime) return day;
  const pad = (n) => String(n).padStart(2, "0");
  return `${day}, ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// Последняя неделя, по которой уже есть хоть одна оценка.
function currentWeek(subjects) {
  let week = 1;
  for (const subject of subjects) {
    for (const type of subject.types) {
      for (const key of Object.keys(type.weeks)) week = Math.max(week, Number(key));
    }
  }
  return week;
}

function dayLabel(iso) {
  const date = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return t.today;
  if (date.toDateString() === yesterday.toDateString()) return t.yesterday;
  return formatDate(iso, false);
}

function columnLabel(column) {
  return /^\d+$/.test(column) ? t.weekTitle(column) : column;
}

function sortedTypes(types) {
  return [...types].sort(
    (a, b) => (TYPE_ORDER.indexOf(a.type) + 1 || 9) - (TYPE_ORDER.indexOf(b.type) + 1 || 9),
  );
}

function haptic() {
  if (tg && tg.HapticFeedback) tg.HapticFeedback.selectionChanged();
}

function emptyState(icon, text) {
  return el("div", { class: "empty-state" }, [
    el("div", { class: "icon", text: icon }),
    ...text.split("\n").flatMap((line, i) => (i ? [el("br"), line] : [line])),
  ]);
}

// ---------- Маркеры и графики ----------

function marker(type, x, y, size, ring) {
  const shape = MARKERS[type] || "diamond";
  const common = { fill: seriesColor(type), stroke: ring, "stroke-width": 2 };
  if (shape === "circle") return svg("circle", { cx: x, cy: y, r: size / 2, ...common });
  if (shape === "square") {
    return svg("rect", { x: x - size / 2, y: y - size / 2, width: size, height: size, rx: 1.5, ...common });
  }
  const h = size * 0.95;
  const points =
    shape === "triangle"
      ? `${x},${y - h / 1.6} ${x - h / 1.7},${y + h / 2.4} ${x + h / 1.7},${y + h / 2.4}`
      : `${x},${y - h / 1.6} ${x + h / 1.6},${y} ${x},${y + h / 1.6} ${x - h / 1.6},${y}`;
  return svg("polygon", { points, ...common });
}

function swatch(type) {
  const icon = svg("svg", { width: 22, height: 12, viewBox: "0 0 22 12", "aria-hidden": "true" });
  icon.append(
    svg("line", { x1: 1, y1: 6, x2: 21, y2: 6, stroke: seriesColor(type), "stroke-width": 2, "stroke-linecap": "round" }),
    marker(type, 11, 6, 7, cssVar("--card")),
  );
  return icon;
}

function absentIcon() {
  const icon = svg("svg", { width: 12, height: 12, viewBox: "0 0 12 12", "aria-hidden": "true" });
  icon.append(
    svg("path", { d: "M2 2 L10 10 M10 2 L2 10", stroke: cssVar("--critical"), "stroke-width": 2.2, "stroke-linecap": "round" }),
  );
  return icon;
}

// Средний балл по неделям — для маленького графика на карточке.
function weeklyAverages(subject, lastWeek) {
  const result = [];
  for (let week = 1; week <= lastWeek; week++) {
    const values = subject.types
      .map((type) => type.weeks[week])
      .filter((value) => typeof value === "number");
    result.push(values.length ? values.reduce((a, b) => a + b, 0) / values.length : null);
  }
  return result;
}

function sparkline(subject, lastWeek) {
  // Реальная ширина карточки — чтобы точка не растягивалась в овал.
  const width = Math.max(document.body.clientWidth - 60, 200);
  const height = 40;
  const values = weeklyAverages(subject, lastWeek);
  const x = (i) => 5 + (i / Math.max(lastWeek - 1, 1)) * (width - 10);
  const y = (v) => height - 5 - (v / 100) * (height - 10);
  const chart = svg("svg", {
    class: "spark",
    viewBox: `0 0 ${width} ${height}`,
    "aria-hidden": "true",
  });

  let path = "";
  let last = null;
  values.forEach((value, i) => {
    if (value === null) return;
    path += `${last === null || last !== i - 1 ? "M" : "L"}${x(i).toFixed(1)},${y(value).toFixed(1)} `;
    last = i;
  });

  if (path) {
    chart.append(svg("path", {
      d: path,
      fill: "none",
      stroke: cssVar("--accent"),
      "stroke-width": 2,
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
      "vector-effect": "non-scaling-stroke",
    }));
  }

  // Точка на последнем значении — где студент сейчас.
  if (last !== null) {
    const dot = svg("circle", {
      cx: x(last), cy: y(values[last]), r: 3.5,
      fill: cssVar("--accent"), stroke: cssVar("--card"), "stroke-width": 2,
      "vector-effect": "non-scaling-stroke",
    });
    chart.append(dot);
  }

  return chart;
}

// Большой график предмета с подсказкой по нажатию.
function subjectChart(subject, lastWeek) {
  const wrap = el("div", { class: "chart-wrap" });
  const width = Math.max(document.body.clientWidth - 60, 260);
  const height = 230;
  const pad = { left: 30, right: 10, top: 10, bottom: 26 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const x = (week) => pad.left + ((week - 1) / Math.max(lastWeek - 1, 1)) * plotW;
  const y = (value) => pad.top + plotH - ((value + 8) / 113) * plotH;
  const ring = cssVar("--card");
  const types = sortedTypes(subject.types);

  const chart = svg("svg", {
    class: "chart",
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label": `${subject.name}: ${t.byWeek}`,
  });

  for (const tick of [0, 25, 50, 75, 100]) {
    chart.append(svg("line", {
      x1: pad.left, x2: width - pad.right, y1: y(tick), y2: y(tick),
      stroke: tick === 50 ? cssVar("--baseline") : cssVar("--grid"),
      "stroke-width": 1,
    }));
    const label = svg("text", { x: pad.left - 6, y: y(tick) + 4, "text-anchor": "end" });
    label.textContent = tick;
    chart.append(label);
  }

  const step = lastWeek > 10 ? 2 : 1;
  for (let week = 1; week <= lastWeek; week += step) {
    const label = svg("text", { x: x(week), y: height - 8, "text-anchor": "middle" });
    label.textContent = week;
    chart.append(label);
  }

  const crosshair = svg("line", {
    y1: pad.top, y2: pad.top + plotH, stroke: cssVar("--baseline"), "stroke-width": 1, visibility: "hidden",
  });
  chart.append(crosshair);

  for (const type of types) {
    let path = "";
    let previous = null;
    for (let week = 1; week <= lastWeek; week++) {
      const value = type.weeks[week];
      if (typeof value !== "number") continue;
      path += `${previous === week - 1 ? "L" : "M"}${x(week).toFixed(1)},${y(value).toFixed(1)} `;
      previous = week;
    }
    chart.append(svg("path", {
      d: path, fill: "none", stroke: seriesColor(type.type),
      "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round",
    }));
  }

  for (const type of types) {
    for (const [week, value] of Object.entries(type.weeks)) {
      if (typeof value === "number") {
        chart.append(marker(type.type, x(+week), y(value), 8, ring));
      } else if (value === "absent") {
        const cx = x(+week);
        const cy = y(-4);
        chart.append(svg("path", {
          d: `M${cx - 4},${cy - 4} L${cx + 4},${cy + 4} M${cx + 4},${cy - 4} L${cx - 4},${cy + 4}`,
          stroke: cssVar("--critical"), "stroke-width": 2.2, "stroke-linecap": "round",
        }));
      }
    }
  }

  // Прозрачный слой ловит касания по всей ширине графика.
  const hit = svg("rect", { x: pad.left - 10, y: 0, width: plotW + 20, height, fill: "transparent" });
  chart.append(hit);

  const tooltip = document.getElementById("tooltip");

  function show(event) {
    const rect = chart.getBoundingClientRect();
    const scale = width / rect.width;
    const px = (event.clientX - rect.left) * scale;
    const week = Math.min(lastWeek, Math.max(1, Math.round(((px - pad.left) / plotW) * (lastWeek - 1) + 1)));
    const rows = types
      .filter((type) => type.weeks[week] !== undefined)
      .map((type) => {
        const value = type.weeks[week];
        return el("div", { class: "tooltip-row" }, [
          value === "absent" ? absentIcon() : swatch(type.type),
          typeLabel(type.type),
          el("b", { text: value === "absent" ? t.absent : formatNumber(value) }),
        ]);
      });

    crosshair.setAttribute("x1", x(week));
    crosshair.setAttribute("x2", x(week));
    crosshair.setAttribute("visibility", "visible");

    tooltip.replaceChildren(
      el("div", { class: "tooltip-title", text: t.weekTitle(week) }),
      ...(rows.length ? rows : [el("div", { class: "item-sub", text: "—" })]),
    );
    tooltip.hidden = false;

    const tipRect = tooltip.getBoundingClientRect();
    const left = rect.left + x(week) / scale;
    const placeLeft = left + 14 + tipRect.width > window.innerWidth - 8;
    tooltip.style.left = `${placeLeft ? left - tipRect.width - 14 : left + 14}px`;
    tooltip.style.top = `${Math.max(8, rect.top + 6)}px`;
  }

  function hide() {
    tooltip.hidden = true;
    crosshair.setAttribute("visibility", "hidden");
  }

  hit.addEventListener("pointermove", show);
  hit.addEventListener("pointerdown", show);
  hit.addEventListener("pointerleave", hide);
  window.addEventListener("scroll", hide, { passive: true });

  wrap.append(chart);
  return wrap;
}

function legend(subject) {
  const types = sortedTypes(subject.types);
  const hasAbsent = types.some((type) => Object.values(type.weeks).includes("absent"));
  return el("div", { class: "legend" }, [
    ...types.map((type) => el("span", {}, [swatch(type.type), typeLabel(type.type)])),
    hasAbsent && el("span", {}, [absentIcon(), t.absentLegend]),
  ]);
}

// ---------- Вкладка «Оценки» ----------

function overallStats(subjects) {
  const values = subjects.flatMap((subject) =>
    subject.types.flatMap((type) => Object.values(type.weeks).filter((v) => typeof v === "number")),
  );
  const average = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  const absences = subjects.reduce((sum, subject) => sum + subject.absences, 0);

  return el("div", { class: "stats" }, [
    el("div", { class: "stat" }, [
      el("div", { class: "stat-value", text: average === null ? "—" : Math.round(average) }),
      el("div", { class: "stat-label", text: t.average }),
    ]),
    el("div", { class: "stat" }, [
      el("div", { class: "stat-value", text: subjects.length }),
      el("div", { class: "stat-label", text: t.subjects }),
    ]),
    el("div", { class: "stat" }, [
      el("div", { class: "stat-value", text: absences }),
      el("div", { class: "stat-label", text: t.absences }),
    ]),
  ]);
}

function subjectCard(subject, lastWeek) {
  const chips = [];
  if (subject.absences) {
    chips.push(el("span", { class: `chip ${subject.absences >= 3 ? "bad" : "warn"}` }, [
      absentIcon(), t.absencesChip(subject.absences),
    ]));
  }
  if (subject.average !== null && subject.average < 60) {
    chips.push(el("span", { class: "chip warn", text: `⚠️ ${t.lowChip}` }));
  }

  return el("button", {
    class: "card subject",
    onclick: () => openSubject(subject.name),
  }, [
    el("div", { class: "subject-head" }, [
      el("div", { class: "subject-name", text: subject.name }),
      el("div", { class: "subject-avg" }, [
        el("strong", { text: subject.average === null ? "—" : Math.round(subject.average) }),
        el("span", { text: t.avgShort }),
      ]),
    ]),
    sparkline(subject, lastWeek),
    chips.length ? el("div", { class: "chips" }, chips) : null,
  ]);
}

function renderGrades() {
  const { subjects } = state.data;
  if (!subjects.length) return [emptyState("📭", t.noGrades)];

  // Мини-графики — до текущей недели, а не до конца семестра.
  const week = currentWeek(subjects);

  return [
    overallStats(subjects),
    el("div", { class: "section-title", text: t.allSubjects }),
    ...subjects.map((subject) => subjectCard(subject, week)),
  ];
}

function weeksTable(subject, lastWeek) {
  const types = sortedTypes(subject.types);
  const weeks = Array.from({ length: lastWeek }, (_, i) => i + 1);

  return el("div", { class: "table-scroll" }, el("table", {}, [
    el("thead", {}, el("tr", {}, [el("th", { text: "" }), ...weeks.map((w) => el("th", { text: w }))])),
    el("tbody", {}, types.map((type) => el("tr", {}, [
      el("td", { text: typeLabel(type.type) }),
      ...weeks.map((week) => {
        const value = type.weeks[week];
        if (value === "absent") return el("td", { class: "absent", text: t.absent });
        if (typeof value === "number") return el("td", { text: formatNumber(value) });
        return el("td", { class: "empty", text: "·" });
      }),
    ]))),
  ]));
}

function totalsTable(subject) {
  const types = sortedTypes(subject.types);
  const columns = [...new Set(types.flatMap((type) => Object.keys(type.totals)))];
  if (!columns.length) return null;

  return el("div", { class: "table-scroll" }, el("table", {}, [
    el("thead", {}, el("tr", {}, [el("th", { text: "" }), ...columns.map((c) => el("th", { text: c }))])),
    el("tbody", {}, types.map((type) => el("tr", {}, [
      el("td", { text: typeLabel(type.type) }),
      ...columns.map((column) => el("td", { text: type.totals[column] || "—" })),
    ]))),
  ]));
}

function renderSubject() {
  const subject = state.data.subjects.find((s) => s.name === state.subject);
  if (!subject) {
    state.subject = null;
    return renderGrades();
  }
  const lastWeek = state.data.last_week;
  const totals = totalsTable(subject);

  return [
    el("div", { class: "detail-title", text: subject.name }),
    el("div", { class: "card" }, [legend(subject), subjectChart(subject, lastWeek)]),
    el("div", { class: "section-title", text: t.byWeek }),
    el("div", { class: "card" }, weeksTable(subject, lastWeek)),
    totals && el("div", { class: "section-title", text: t.totals }),
    totals && el("div", { class: "card" }, totals),
  ];
}

// ---------- Вкладка «Изменения» ----------

function renderChanges() {
  const { changes } = state.data;
  if (!changes.length) return [emptyState("✨", t.noChanges)];

  const groups = new Map();
  for (const change of changes) {
    const label = dayLabel(change.at);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(change);
  }

  return [...groups].flatMap(([label, items]) => [
    el("div", { class: "section-title", text: label }),
    el("div", { class: "card" }, items.map((change) => el("div", { class: "list-item" }, [
      el("div", { class: "badge", text: KIND_ICONS[change.kind] || "•", title: t.kinds[change.kind] }),
      el("div", { class: "item-main" }, [
        el("div", { class: "item-title", text: change.subject }),
        el("div", { class: "item-sub", text: `${typeLabel(change.type)} · ${columnLabel(change.column)} · ${t.kinds[change.kind] || ""}` }),
      ]),
      el("div", { class: "item-value" }, [
        change.old ? el("span", { class: "old", text: change.old }) : null,
        change.new || "—",
      ]),
    ]))),
  ]);
}

// ---------- Вкладка «Кесте» ----------

// День недели 1–7 (понедельник — 1) для даты YYYY-MM-DD.
function isoWeekday(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  return ((new Date(year, month - 1, day).getDay() + 6) % 7) + 1;
}

function lessonCard(lesson) {
  const details = [typeLabel(lesson.type)];
  if (lesson.tutor) details.push(lesson.tutor);

  let place;
  if (lesson.online) {
    place = el("div", { class: "lesson-place" }, [
      `💻 ${t.online}`,
      lesson.link
        ? el("button", {
            class: "link-button",
            text: t.join,
            onclick: () => (tg ? tg.openLink(lesson.link) : window.open(lesson.link, "_blank", "noopener")),
          })
        : null,
    ]);
  } else {
    const parts = [lesson.room ? t.room(lesson.room) : null, lesson.building].filter(Boolean);
    place = parts.length ? el("div", { class: "lesson-place", text: `📍 ${parts.join(", ")}` }) : null;
  }

  return el("div", { class: "lesson" }, [
    el("div", { class: "lesson-time" }, [
      el("strong", { text: lesson.start }),
      el("span", { text: lesson.finish }),
    ]),
    el("div", { class: "lesson-main" }, [
      el("div", { class: "item-title", text: lesson.subject }),
      el("div", { class: "item-sub", text: details.join(" · ") }),
      place,
    ]),
  ]);
}

function renderSchedule() {
  const schedule = state.data.schedule;
  if (!schedule) return [emptyState("📅", t.noSchedule)];

  const todayIndex = isoWeekday(state.data.today);
  const hasLessons = (day) => (schedule.days[String(day)] || []).length > 0;
  const days = [1, 2, 3, 4, 5, 6, 7].filter((day) => day <= 6 || hasLessons(day));

  if (state.day === null) state.day = todayIndex <= 6 || hasLessons(7) ? todayIndex : 1;

  const chips = el("div", { class: "day-chips" }, days.map((day) => el("button", {
    class: `day-chip${day === state.day ? " active" : ""}${hasLessons(day) ? "" : " empty"}`,
    onclick: () => {
      if (state.day === day) return;
      haptic();
      state.day = day;
      render();
    },
  }, [
    el("span", { text: t.weekdaysShort[day - 1] }),
    day === todayIndex ? el("i", { class: "dot" }) : null,
  ])));

  const lessons = schedule.days[String(state.day)] || [];
  const title = `${t.weekdays[state.day - 1]}${state.day === todayIndex ? ` · ${t.todayMark}` : ""}`;

  return [
    schedule.week ? el("div", { class: "section-title", text: t.semesterWeek(schedule.week) }) : null,
    chips,
    el("div", { class: "section-title", text: title }),
    lessons.length
      ? el("div", { class: "card" }, lessons.map(lessonCard))
      : emptyState("🎉", t.noLessons),
  ];
}

// ---------- Вкладка «Заметки» ----------

function renderNotes() {
  const { notes } = state.data;
  if (!notes.length) return [emptyState("📝", t.noNotes)];

  const now = Date.now();

  return notes.map((note) => {
    const upcoming = note.remind_at && new Date(note.remind_at).getTime() > now;
    const actions = [];

    if (note.remind_at) {
      actions.push(el("span", { class: `chip ${upcoming ? "" : "warn"}`, text: `⏰ ${formatDate(note.remind_at)}` }));
    }
    if (note.url) {
      actions.push(el("button", {
        class: "link-button",
        text: `🔗 ${t.openLink}`,
        onclick: () => (tg ? tg.openLink(note.url) : window.open(note.url, "_blank", "noopener")),
      }));
    }

    return el("div", { class: "card" }, [
      el("div", { class: "item-title", text: note.topic }),
      note.text && note.text !== note.topic ? el("div", { class: "note-text", text: note.text }) : null,
      actions.length ? el("div", { class: "note-actions" }, actions) : null,
    ]);
  });
}

// ---------- Навигация ----------

function renderTabs() {
  const tabs = document.getElementById("tabs");
  const counts = { changes: state.data.changes.length, notes: state.data.notes.length };

  tabs.replaceChildren(...Object.entries(t.tabs).map(([key, label]) => el("button", {
    role: "tab",
    "aria-selected": String(state.tab === key),
    onclick: () => {
      if (state.tab === key && !state.subject) return;
      haptic();
      state.tab = key;
      state.subject = null;
      render();
      window.scrollTo({ top: 0 });
    },
  }, [label, counts[key] ? el("span", { class: "count", text: counts[key] }) : null])));
}

function render() {
  document.getElementById("tooltip").hidden = true;
  renderTabs();

  let content;
  if (state.tab === "grades") content = state.subject ? renderSubject() : renderGrades();
  else if (state.tab === "schedule") content = renderSchedule();
  else if (state.tab === "changes") content = renderChanges();
  else content = renderNotes();

  document.getElementById("app").replaceChildren(...content.filter(Boolean));

  if (tg && tg.BackButton) {
    if (state.subject) tg.BackButton.show();
    else tg.BackButton.hide();
  }
}

function openSubject(name) {
  haptic();
  state.subject = name;
  render();
  window.scrollTo({ top: 0 });
}

function closeSubject() {
  state.subject = null;
  render();
}

function applyTheme() {
  const scheme = tg && tg.colorScheme ? tg.colorScheme : null;
  if (scheme) document.documentElement.dataset.scheme = scheme;
}

function showMessage(icon, text) {
  document.getElementById("tabs").replaceChildren();
  document.getElementById("app").replaceChildren(emptyState(icon, text));
}

async function load() {
  applyTheme();

  if (tg) {
    tg.ready();
    tg.expand();
    tg.onEvent("themeChanged", () => {
      applyTheme();
      if (state.data) render();
    });
    if (tg.BackButton) tg.BackButton.onClick(closeSubject);
  }

  const initData = tg ? tg.initData : "";
  const userLanguage = tg && tg.initDataUnsafe && tg.initDataUnsafe.user
    ? tg.initDataUnsafe.user.language_code
    : "";
  t = TEXTS[userLanguage === "ru" ? "ru" : "kk"];

  if (!initData) {
    showMessage("📱", t.openInTelegram);
    return;
  }

  try {
    const response = await fetch("/api/me", { headers: { Authorization: `tma ${initData}` } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
  } catch (error) {
    showMessage("⚠️", t.loadError);
    return;
  }

  t = TEXTS[state.data.language] || TEXTS.kk;
  document.documentElement.lang = state.data.language;

  if (state.data.fetched_at) {
    document.getElementById("updated").textContent = `${t.updated}: ${formatDate(state.data.fetched_at)}`;
  }

  render();
}

load();
