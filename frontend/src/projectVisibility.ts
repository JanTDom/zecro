import type { Project } from './types/project';

// Historic QA records remain available in an expandable archive on the
// projects page. They must not masquerade as choices in the main workflow.
export const isTechnicalProject = (project: Project): boolean =>
  /\b(test\d*|qa|preflight|lifecycle|integration|db arch|audit)\b/i.test(project.name) ||
  /^the daily chronicle$/i.test(project.name.trim()) ||
  /automated test suite|^qa$/i.test(project.description.trim());
