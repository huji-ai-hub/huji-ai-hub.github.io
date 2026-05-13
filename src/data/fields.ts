// Research field metadata for both languages.
// Used by /research/[field] and /he/research/[field] pages.

export interface FieldData {
  slug: string;
  title: string;
  titleHe: string;
  subtitle: string;
  subtitleHe: string;
  intro: string;
  introHe: string;
  gradient: string;
  image?: string;
}

export const FIELDS: FieldData[] = [
  {
    slug: 'machine-perception',
    title: 'Machine Perception',
    titleHe: 'תפיסה ממוחשבת',
    subtitle: 'Teaching machines to see, hear, and interpret the visual and acoustic world.',
    subtitleHe: 'ללמד מכונות לראות, לשמוע ולפענח את העולם החזותי והאקוסטי.',
    intro: 'The Machine Perception Group develops algorithms and methods that allow computers to reach the remarkable performance of humans, and in some cases even surpass human ability, across vision, video, audio, and 3D scene understanding.',
    introHe: 'קבוצת התפיסה הממוחשבת מפתחת אלגוריתמים ושיטות המאפשרים למחשבים להגיע לרמת הביצוע יוצאת הדופן של בני אדם, ובמקרים מסוימים אף לעלות עליה, בתחומי הראייה, הווידאו, האודיו והבנת סצנות תלת-ממדיות.',
    gradient: 'linear-gradient(135deg, #1a3a4a 0%, #2d6b7a 100%)',
    image: '/images/pexels-googledeepmind-17483867.jpg',
  },
  {
    slug: 'language-cognition',
    title: 'Language and Cognition',
    titleHe: 'שפה וקוגניציה',
    subtitle: 'Building systems that understand, generate, and reason about language.',
    subtitleHe: 'בניית מערכות המבינות, מייצרות ומסיקות שפה.',
    intro: 'Our NLP and cognitive science labs work on the foundations of how machines and humans handle meaning, from large language models and multilingual systems to causal reasoning, child language acquisition, and linguistic typology.',
    introHe: 'מעבדות עיבוד השפה הטבעית ומדעי הקוגניציה שלנו עוסקות ביסודות הדרך שבה מכונות ובני אדם מטפלים במשמעות, ממודלי שפה גדולים ומערכות רב-לשוניות ועד הסקה סיבתית, רכישת שפה אצל ילדים וטיפולוגיה לשונית.',
    gradient: 'linear-gradient(135deg, #3a2a5a 0%, #6b5a8a 100%)',
    image: '/images/pexels-googledeepmind-25626428.jpg',
  },
  {
    slug: 'foundations-of-learning',
    title: 'Foundations of Learning',
    titleHe: 'יסודות הלמידה',
    subtitle: 'The mathematical and theoretical principles behind modern AI.',
    subtitleHe: 'העקרונות המתמטיים והתאורטיים שמאחורי AI מודרני.',
    intro: 'Theoretical foundations of machine learning, including learning theory, optimization, and the principles enabling efficient inference at the scale of modern foundation models.',
    introHe: 'יסודות תאורטיים של למידת מכונה, כולל תאוריה של למידה, אופטימיזציה והעקרונות המאפשרים הסקה יעילה בקנה המידה של מודלי יסוד מודרניים.',
    gradient: 'linear-gradient(135deg, #2a4a3a 0%, #4a7a5a 100%)',
    image: '/images/pexels-googledeepmind-25626509.jpg',
  },
  {
    slug: 'biomed',
    title: 'AI in BioMed',
    titleHe: 'AI ברפואה ובמדעי החיים',
    subtitle: 'AI for genomics, drug discovery, surgery, and clinical care.',
    subtitleHe: 'בינה מלאכותית לגנומיקה, גילוי תרופות, ניתוחים וטיפול קליני.',
    intro: 'Bridging machine learning with biology and medicine, from single-cell genomics and protein structure to surgical navigation, drug development, and probabilistic models of gene regulation.',
    introHe: 'גישור בין למידת מכונה לביולוגיה ולרפואה, מגנומיקה של תאים בודדים ומבנה חלבונים ועד ניווט כירורגי, פיתוח תרופות ומודלים הסתברותיים של ויסות גנים.',
    gradient: 'linear-gradient(135deg, #4a2a3a 0%, #7a5a6a 100%)',
    image: '/images/pexels-diva-32021111.jpg',
  },
  {
    slug: 'multi-agent',
    title: 'Multi-agent Environments',
    titleHe: 'סביבות רב-סוכניות',
    subtitle: 'How autonomous agents coordinate, compete, and behave at scale.',
    subtitleHe: 'איך סוכנים אוטונומיים מתואמים, מתחרים ומתנהגים בקנה מידה גדול.',
    intro: 'Research at the intersection of machine learning, game theory, and formal verification, covering privacy, fairness, AI policy, multi-agent verification, and strategic behavior of learning systems.',
    introHe: 'מחקר בנקודת ההצטלבות של למידת מכונה, תורת המשחקים ואימות פורמלי, כולל פרטיות, הוגנות, מדיניות AI, אימות רב-סוכני והתנהגות אסטרטגית של מערכות לומדות.',
    gradient: 'linear-gradient(135deg, #2a3a4a 0%, #5a7a8a 100%)',
    image: '/images/pexels-rostislav-30767251.jpg',
  },
  {
    slug: 'cyber-crypto',
    title: 'Systems & Cyber',
    titleHe: 'מערכות וסייבר',
    subtitle: 'AI for security, cryptography, networks, and hardware acceleration.',
    subtitleHe: 'בינה מלאכותית לאבטחה, קריפטוגרפיה, רשתות וזירוז חומרה.',
    intro: 'Where AI meets systems engineering, from formally verifying neural networks to faster matrix multiplication, datacenter optimization, and the security and privacy implications of large-scale models.',
    introHe: 'המקום שבו AI פוגש הנדסת מערכות, מאימות פורמלי של רשתות נוירונים ועד כפל מטריצות מהיר יותר, אופטימיזציה של מרכזי נתונים והשלכות אבטחה ופרטיות של מודלים בקנה מידה גדול.',
    gradient: 'linear-gradient(135deg, #3a3a2a 0%, #6a6a4a 100%)',
    image: '/images/pexels-googledeepmind-17483870.jpg',
  },
  {
    slug: 'data-science',
    title: 'Data Science',
    titleHe: 'מדעי הנתונים',
    subtitle: 'Making sense of the world through data, at every scale.',
    subtitleHe: 'הבנת העולם באמצעות נתונים, בכל קנה מידה.',
    intro: 'From data quality and pipeline accountability to large-scale knowledge discovery and computational physics, extracting structure from messy real-world data.',
    introHe: 'מאיכות נתונים ואחריותיות במערכות מידע ועד גילוי ידע בקנה מידה גדול ופיזיקה חישובית, חילוץ מבנה מנתונים בעולם האמיתי.',
    gradient: 'linear-gradient(135deg, #1a2a4a 0%, #4a5a7a 100%)',
    image: '/images/pexels-googledeepmind-18069814.jpg',
  },
  {
    slug: 'human-centered',
    title: 'Human-Centered AI',
    titleHe: 'AI ממוקד אדם',
    subtitle: 'AI that serves people, clinically, socially, and politically.',
    subtitleHe: 'בינה מלאכותית בשירות בני אדם, קלינית, חברתית ופוליטית.',
    intro: 'Research on AI applications and governance that center human well-being, from VR-based clinical interventions to AI accountability frameworks and the role of AI in public sector decision-making.',
    introHe: 'מחקר על יישומי AI וממשל הממקדים את רווחת האדם, מהתערבויות קליניות מבוססות מציאות מדומה ועד מסגרות אחריותיות AI ותפקיד ה-AI בקבלת החלטות במגזר הציבורי.',
    gradient: 'linear-gradient(135deg, #4a3a1a 0%, #7a6a4a 100%)',
    image: '/images/pexels-steve-10194141.jpg',
  },
];

export function getField(slug: string): FieldData | undefined {
  return FIELDS.find(f => f.slug === slug);
}
