You are an expert in prompt quality evaluation. Carefully read the image-generation prompt below and judge whether each statement is true.

Required questions (answer each with "yes" or "no"):
  [R01] Is the prompt non-empty and does it contain actionable image description information (rather than only a title or short phrase)?
  [R02] Does the prompt clearly specify a "subject object" or "main visual subject" (such as an infographic, chart, illustration, poster, etc.)?
  [R03] Does the prompt include at least one type of "structured information" (for example: sections/regions/modules/steps/order/comparison/list, in any form)?
  [R04] Does the prompt include at least one type of visual description (such as style, color scheme, background, composition, visual mood, etc.)?
  [R05] Does the prompt include at least one concrete visual element (such as icons, people, shapes, arrows, borders, etc.)?
  [R06] Does the prompt include content details that can be directly drawn or typeset (such as text labels, explanatory text, module content, etc.)?
  [R07] Does the prompt reflect organizational relationships among elements (such as positional, sequential, connection, or hierarchical relationships)?
  [R08] Does the prompt provide sufficient length and detail density to support stable full-scene generation by the LLM?

Optional questions (answer each with yes or no):
  [O01] Does the prompt include descriptions of causal relationships or logical reasoning?
  [O02] Does the prompt mention data encoding or visualization methods?
  [O03] Does the prompt distinguish information with different importance or priorities?
  [O04] Does the prompt describe background context or scene settings?
  [O05] Does the prompt mention dynamic effects or interactive elements (such as arrows and connector lines)?
  [O06] Does the prompt provide specific material/texture descriptions (metal/wood/transparent, etc.)?
  [O07] Does the prompt incorporate cultural meaning or symbolic significance?
  [O08] Does the prompt evoke an emotional atmosphere (solemn/lively/mysterious, etc.)?
  [O09] Does the prompt appropriately use domain-relevant English terminology?
  [O10] Does the prompt distinguish how Chinese and English text labels are used?
  [O11] Does the prompt include summary or conclusion-oriented content descriptions?
  [O12] Does the prompt specify the target audience or application scenario?

Output format (strict JSON, no additional content):
{
  "required_results": [
    {"id": "R01", "answer": "yes"},
    {"id": "R02", "answer": "no"},
    ...
  ],
  "optional_results": [
    {"id": "O01", "answer": "yes"},
    {"id": "O02", "answer": "no"},
    ...
  ]
}

Prompt content below:
