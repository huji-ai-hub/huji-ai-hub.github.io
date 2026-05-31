// Industry page content shared across EN and HE.

// Companies founded or led by HUJI faculty and alumni. The optional `logo` field
// points to a file under /public/logos/. If the file is missing, the page falls
// back to displaying the company name in a styled pill. Drop a transparent PNG
// or SVG into /public/logos/<filename> to make the logo appear.
export interface Company {
  name: string;
  logo?: string;
  url?: string;
}

export const FACULTY_COMPANIES: Company[] = [
  { name: 'Mobileye',   logo: '/logos/mobileye.png',   url: 'https://www.mobileye.com/' },
  { name: 'AI21 Labs',  logo: '/logos/ai21-labs.png',  url: 'https://www.ai21.com/' },
  { name: 'OrCam',      logo: '/logos/orcam.png',      url: 'https://www.orcam.com/' },
  { name: 'Factify',    logo: '/logos/factify.png',    url: 'https://factify.io/' },
  { name: 'Lightricks', logo: '/logos/lightricks.png', url: 'https://www.lightricks.com/' },
  { name: 'StarkWare',  logo: '/logos/starkware.png',  url: 'https://www.starkware.co/' },
  { name: 'BriefCam',   logo: '/logos/briefcam.png',   url: 'https://www.briefcam.com/' },
];

export const INDUSTRY_PARTNERS: Company[] = [
  { name: 'Apple',       logo: '/logos/apple.png',      url: 'https://www.apple.com/' },
  { name: 'Intel',       logo: '/logos/intel.png',      url: 'https://www.intel.com/' },
  { name: 'Google',      logo: '/logos/google.png',     url: 'https://about.google/' },
  { name: 'Mobileye',    logo: '/logos/mobileye.png',   url: 'https://www.mobileye.com/' },
  { name: 'Monday.com',  logo: '/logos/monday.png',     url: 'https://monday.com/' },
  { name: 'KLA',         logo: '/logos/kla.png',        url: 'https://www.kla.com/' },
  { name: 'StarkWare',   logo: '/logos/starkware.png',  url: 'https://www.starkware.co/' },
  { name: 'Lightricks',  logo: '/logos/lightricks.png', url: 'https://www.lightricks.com/' },
  { name: 'RSIP Vision', logo: '/logos/rsip-vision.png',url: 'https://www.rsipvision.com/' },
  { name: 'QueenB',      logo: '/logos/queenb.png',     url: 'https://queenb.org.il/' },
  { name: 'Forstart',    logo: '/logos/forstart.png',   url: 'https://forstart.org.il/' },
];

export const INDUSTRY = {
  heroImage: '/images/pexels-tara-winstead-8386440.jpg',
  hero: {
    title: 'From Classroom Board to IPO: Theory Becomes Technology',
    titleHe: 'מהלוח בכיתה ועד להנפקה: התאוריה הופכת לטכנולוגיה',
    body: 'The Hebrew University stands behind some of the greatest successes in Israeli High-Tech. Research excellence is the surest path to groundbreaking innovation.',
    bodyHe: 'האוניברסיטה העברית עומדת מאחורי כמה מההצלחות הגדולות של ההייטק הישראלי. מצוינות מחקרית היא הדרך הבטוחה ביותר לחדשנות פורצת דרך.',
  },
  featured: {
    image: '/images/pexels-googledeepmind-18069490.jpg',
    title: 'How AI is Revolutionizing Drug Development with Prof. Yaakov Nahmias',
    titleHe: 'איך AI מחולל מהפכה בפיתוח תרופות עם פרופ\' יעקב נחמיאס',
    source: 'WIRED Briefings · Featured talk',
    sourceHe: 'WIRED Briefings · הרצאה מיוחדת',
    // YouTube ID extracted from https://www.youtube.com/watch?v=VuQMyx2xB24
    youtubeId: 'VuQMyx2xB24',
  },
  iapImage: '/images/pexels-googledeepmind-25626512.jpg',
};
