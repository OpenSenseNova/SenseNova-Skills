import { getLanguage, t } from './i18n.js';

// Display translations are keyed by case ID and separate from the versioned prompt catalog.
const englishCases = {
  'feishu-case-002': { name: "Layered paper sculpture" },
  'feishu-case-003': { name: "Line art over travel photography" },
  'feishu-case-004': { name: "Washi tape collage" },
  'feishu-case-007': { name: "Crayon doodles" },
  'feishu-case-011': { name: "Retro risograph print" },
  'feishu-case-012': { name: "Photo collage with doodles" },
  'feishu-case-013': { name: "Dimensional paper-cut illustration" },
  'feishu-case-014': { name: "City illustration" },
  'feishu-case-015': { name: "Impasto oil painting · Cats by a pond" },
  'feishu-case-016': { name: "Line art over photography · A second world" },
  'feishu-case-018': { name: "East Asian aesthetics" },
  'feishu-case-019': { name: "Watercolor and line art · Lotus pond" },
  'feishu-case-020': { name: "Retro risograph illustration" },
  'feishu-case-021': { name: "Cute 3D doll" },
  'feishu-case-022': { name: "Character design reference sheet" },
  'feishu-case-025': { name: "Layered journal collage" },
  'feishu-case-028': { name: "3D miniature diorama" },
  'feishu-case-029': { name: "Rough hand-drawn sketch" },
  'feishu-case-030': { name: "Impasto oil painting · Diptych" },
  'feishu-case-032': { name: "Architectural line drawing" },
  'feishu-case-037': { name: "Relaxed outdoor photo journal" },
  'feishu-case-038': { name: "Colored pencil illustration" },
  'feishu-case-039': {
    name: "Minimalist hand-drawn illustration",
  },
  'feishu-case-040': { name: "Handcrafted-style infographic" },
  'feishu-case-041': { name: "Journal collage" },
  'feishu-case-042': {
    name: "Out-of-frame typography",
  },
  'feishu-case-043': { name: "Illustrated journal page" },
  'feishu-case-044': { name: "Retro computer graphics" },
  'feishu-case-045': { name: "Travel photo scrapbook" },
  'feishu-case-046': { name: "Miniature diorama" },
  'feishu-case-047': { name: "Watercolor figure sketch" },
  'feishu-case-048': { name: "Modern picture-book illustration" },
  'feishu-case-049': { name: "Monochrome editorial print" },
  'feishu-case-050': { name: "Impasto oil painting" },
  'feishu-case-051': { name: "Photo print collage" },
  'feishu-case-052': { name: "Photo recomposition" },
  'feishu-case-053': { name: "Custom stamp" },
  'feishu-case-056-japanese': { name: "Japanese magazine portrait · Sweet style" },
  'feishu-case-056-y2k': { name: "Japanese magazine portrait · Pink and black Y2K" },
  'feishu-case-057': { name: "Hand-drawn office collage" },
  'feishu-case-058': { name: "Y2K poster" },
  'feishu-case-059': { name: "3D collectible figure" },
  'feishu-case-060': { name: "Paper craft poster" },
  'feishu-case-062': { name: "Impasto oil painting · Miniature landscape" },
  'feishu-case-063': {
    name: "Architectural shadow analysis",
  },
  'feishu-case-064': { name: "Retro glitch art" },
  'feishu-case-065': { name: "Scientific illustration" },
  'feishu-case-066': { name: "Stylized illustration" },
  'feishu-case-067': { name: "Denis Villeneuve-inspired cinematography" },
};

const roleKeys = new Map([
  ['需要改编的原始照片', 'sourcePhotoRole'],
  ['中央主图', 'centerPhotoRole'],
  ['横向辅助照片', 'landscapePhotoRole'],
  ['竖向辅助照片', 'portraitPhotoRole'],
  ['补充参考图', 'referenceImage'],
]);

export function inputRoleLabel(role) {
  const key = roleKeys.get(role);
  return key ? t(key) : role;
}

export function originalPromptLabel(prompt, key = 'originalPromptLabel') {
  const label = t(key);
  return getLanguage() === 'en' && /\p{Script=Han}/u.test(prompt)
    ? t('promptContainsChinese', { label }) : label;
}

export function casePrompt(item, language = getLanguage()) {
  return item.promptLocales?.[language] || item.originalPrompt;
}

export function caseCopy(item) {
  const translation = getLanguage() === 'en' && Object.hasOwn(englishCases, item.id) ? englishCases[item.id] : null;
  const { recipe } = item;
  const name = translation?.name || item.name;
  const copy = {
    name,
    category: item.category === '图像生成' ? t('generation') : item.category === '图片编辑' ? t('editing') : item.category,
    style: item.style,
    effect: recipe.effect,
    suggestion: item.suggestion,
    beforeLabel: example => example.beforeLabel && example.beforeLabel !== '原图' ? example.beforeLabel : t('before'),
    inputRoles: recipe.inputRoles.map(inputRoleLabel),
    guidance: recipe.preserve.length
      ? t('preserveCaseGuidance', { features: recipe.preserve.join(t('listSeparator')) }) : t('defaultCaseGuidance'),
    editable: recipe.editable.length
      ? t('editableCaseDetails', { features: recipe.editable.join(t('listSeparator')) }) : t('defaultCaseDetails'),
  };
  if (!translation) return copy;

  copy.suggestion = t(item.mode === 'edit' ? 'caseEditSuggestion' : 'caseGenerationSuggestion');
  copy.style = item.id === 'feishu-case-050' ? t('impastoStyle') : t('importedCaseStyle', { name });
  copy.effect = item.id === 'feishu-case-050' ? t('impastoEffect') : t('importedCaseEffect', { name });
  return copy;
}
