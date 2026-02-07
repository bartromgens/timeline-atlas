export const CATEGORY_COLORS = [
  '#1976d2',
  '#c62828',
  '#2e7d32',
  '#f9a825',
  '#6a1b9a',
  '#00838f',
  '#d84315',
  '#283593',
  '#558b2f',
  '#ad1457',
];

const UNCATEGORIZED_COLOR = '#757575';

export function colorForCategory(categoryId: number | null): string {
  if (categoryId == null) return UNCATEGORIZED_COLOR;
  const index = Math.abs(categoryId) % CATEGORY_COLORS.length;
  return CATEGORY_COLORS[index];
}
