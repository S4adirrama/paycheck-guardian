export const NARRATION =
  'Your paycheck shouldn’t disappear without answers. Recurring charges, duplicates, and everyday spending patterns can hide in plain sight. Paycheck Guardian reviews local transaction evidence and turns it into a short, verified plan — without connecting to your bank. Run the demo and see what could stay in your account before the next paycheck. Every recommendation is independently checked. Open the evidence to inspect the transactions, the calculation, the confidence, and the caveat. Then you decide: approve a local simulation, or dismiss it instantly. No merchant is contacted. No real cancellation happens. And the privacy-safe agent trace shows how every tool call and verification decision was made. Paycheck Guardian. Verified. Explainable. In your control.';

export const DISCLOSURE = 'Educational prototype. No real financial actions.';

export const METRICS = {
  beforePaycheck: '$44.87',
  monthly: '$97.49',
  evidenceMonthly: '$63.00',
  evidencePaycheck: '$29.00',
} as const;

export type CaptionRecord = {
  from: number;
  duration: number;
  text: string;
  accent?: string;
};

export const CAPTIONS: CaptionRecord[] = [
  {from: 12, duration: 145, text: 'Your paycheck shouldn’t disappear without answers.', accent: 'answers'},
  {from: 195, duration: 170, text: 'Hidden patterns can be difficult to review safely.', accent: 'safely'},
  {from: 414, duration: 150, text: 'Local evidence. No bank connection.', accent: 'Local'},
  {from: 630, duration: 250, text: 'A short, independently verified plan.', accent: 'verified'},
  {from: 955, duration: 225, text: 'Every estimate shows its evidence and calculation.', accent: 'evidence'},
  {from: 1250, duration: 185, text: 'You decide. No merchant is contacted.', accent: 'You decide'},
  {from: 1490, duration: 130, text: 'A privacy-safe trace shows every decision.', accent: 'privacy-safe'},
  {from: 1650, duration: 150, text: DISCLOSURE},
];
