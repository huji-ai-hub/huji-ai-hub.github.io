// Homepage content shared across English and Hebrew versions.
// Edit here to update both languages at once (where copy is identical) or both fields (where it differs).

export interface PillarCard {
  href: string;
  hrefHe: string;
  label: string;
  labelHe: string;
  image: string;
}

export interface NewsCard {
  href: string;
  hrefHe: string;
  label: string;
  labelHe: string;
  image: string;
}

export const HOMEPAGE = {
  heroImage: '/images/pexels-googledeepmind-17483874.jpg',

  hero: {
    title: 'AI at the Hebrew University',
    titleHe: 'בינה מלאכותית באוניברסיטה העברית',
    body: 'Artificial Intelligence impacts every aspect of life. At the Hebrew University, we research and teach diverse disciplines in the foundations, applications, and implications of AI',
    bodyHe: 'בינה מלאכותית משפיעה על כל תחום בחיינו. באוניברסיטה העברית אנו חוקרים ומלמדים תחומים מגוונים ביסודות, היישומים וההשלכות של בינה מלאכותית.',
  },

  pillars: [
    {
      href: '/research',
      hrefHe: '/he/research',
      label: 'Research',
      labelHe: 'מחקר',
      image: '/images/pexels-googledeepmind-25630347.jpg',
    },
    {
      href: '/academics',
      hrefHe: '/he/academics',
      label: 'Academics',
      labelHe: 'לימודים',
      image: '/images/pexels-cottonbro-6153344.jpg',
    },
    {
      href: '/industry',
      hrefHe: '/he/industry',
      label: 'Industry',
      labelHe: 'תעשייה',
      image: '/images/pexels-tara-winstead-8386421.jpg',
    },
  ] satisfies PillarCard[],

  spotlight: {
    image: '/images/pexels-googledeepmind-18069696.jpg',
    title: 'Mastering the Tech of Tomorrow: Computer Science in the AI Era',
    titleHe: 'לשלוט בטכנולוגיה של מחר: מדעי המחשב בעידן ה-AI',
    body: [
      "The new Computer Science program at the Hebrew University, featuring an AI specialization, is designed for students aspiring to understand how this generation's tools work — and to develop the next generation's tools. The program was developed by leading researchers, combining theoretical depth with practical application.",
      'It provides a solid mathematical foundation and deep exposure to modern models, training graduates capable of analyzing, training, and critically examining complex systems. Here, you acquire the knowledge needed to lead R&D in a changing technological environment.',
    ],
    bodyHe: [
      'התוכנית החדשה למדעי המחשב באוניברסיטה העברית, הכוללת התמחות בבינה מלאכותית, מיועדת לסטודנטים השואפים להבין כיצד פועלים הכלים של הדור הנוכחי — ולפתח את הכלים של הדור הבא. התוכנית פותחה על ידי חוקרים מובילים, ומשלבת עומק תיאורטי עם יישום מעשי.',
      'היא מספקת בסיס מתמטי מוצק וחשיפה מעמיקה למודלים מודרניים, ומכשירה בוגרים המסוגלים לנתח, לאמן ולבחון באופן ביקורתי מערכות מורכבות.',
    ],
    cta: 'Details & Registration →',
    ctaHe: 'פרטים והרשמה ←',
    ctaHref: '/academics',
    ctaHrefHe: '/he/academics',
  },

  newsTitle: 'Latest in AI at Hebrew University',
  newsTitleHe: 'חדש ב-AI באוניברסיטה העברית',

  news: [
    {
      href: '/academics',
      hrefHe: '/he/academics',
      label: 'CS AI Program',
      labelHe: 'תוכנית AI במדעי המחשב',
      image: '/images/pexels-googledeepmind-25626519.jpg',
    },
    {
      href: '/academics',
      hrefHe: '/he/academics',
      label: 'New Course — Programming with AI Agents',
      labelHe: 'קורס חדש — תכנות עם סוכני AI',
      image: '/images/pexels-googledeepmind-18069241.jpg',
    },
  ] satisfies NewsCard[],
};
