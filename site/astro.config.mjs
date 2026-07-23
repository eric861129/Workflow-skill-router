import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { unlink } from 'node:fs/promises';

const siteUrl = 'https://huangchiyu.com';
const basePath = '/Workflow-skill-router';
const repoUrl = 'https://github.com/eric861129/Workflow-skill-router';
const ogImage = `${siteUrl}${basePath}/og/workflow-skill-router.png`;

async function unlinkGeneratedAsset(assetUrl) {
  try {
    await unlink(assetUrl);
  } catch (error) {
    if (error?.code !== 'ENOENT') throw error;
  }
}

const excludeLegacySiteAssets = {
  name: 'exclude-legacy-site-assets',
  hooks: {
    'astro:build:done': async ({ dir }) => {
      await unlinkGeneratedAsset(new URL('assets/workflow_skill_rout-GIF.gif', dir));
      await unlinkGeneratedAsset(new URL('assets/workflow-skill-router-60s-demo.gif', dir));
      await unlinkGeneratedAsset(new URL('assets/workflow-skill-router-demo-poster.png', dir));
    },
  },
};

export default defineConfig({
  site: siteUrl,
  base: basePath,
  integrations: [
    starlight({
      title: 'Workflow Skill Router',
      description:
        'Runtime-aware skill routing for single tasks, phased work, and managed goals.',
      defaultLocale: 'root',
      locales: {
        root: {
          label: 'English',
          lang: 'en',
        },
        'zh-tw': {
          label: '繁體中文',
          lang: 'zh-TW',
        },
      },
      logo: {
        light: './src/assets/routing-mark-light.svg',
        dark: './src/assets/routing-mark-dark.svg',
      },
      components: {
        Head: './src/components/Head.astro',
        PageSidebar: './src/components/DocsPageSidebar.astro',
        PageTitle: './src/components/PageTitle.astro',
      },
      disable404Route: true,
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: repoUrl,
        },
      ],
      customCss: ['./src/styles/custom.css'],
      head: [
        {
          tag: 'meta',
          attrs: {
            name: 'keywords',
            content:
              'AI agent skill routing pattern, agent sprawl, skill selection sprawl, workflow router, Codex skills, multi-skill agents, agent governance, developer tools',
          },
        },
        {
          tag: 'meta',
          attrs: {
            name: 'theme-color',
            content: '#08111f',
          },
        },
        {
          tag: 'meta',
          attrs: {
            property: 'og:type',
            content: 'website',
          },
        },
        {
          tag: 'meta',
          attrs: {
            property: 'og:site_name',
            content: 'Workflow Skill Router',
          },
        },
        {
          tag: 'meta',
          attrs: {
            property: 'og:image',
            content: ogImage,
          },
        },
        {
          tag: 'meta',
          attrs: {
            property: 'og:image:alt',
            content: 'Workflow Skill Router routing pattern preview',
          },
        },
        {
          tag: 'meta',
          attrs: {
            name: 'twitter:card',
            content: 'summary_large_image',
          },
        },
        {
          tag: 'meta',
          attrs: {
            name: 'twitter:image',
            content: ogImage,
          },
        },
        {
          tag: 'meta',
          attrs: {
            name: 'github:repository',
            content: repoUrl,
          },
        },
      ],
      sidebar: [
        {
          label: 'Start',
          translations: {
            'zh-TW': '開始',
          },
          items: [
            { slug: '' },
            { slug: 'guides/quickstart' },
            { slug: 'guides/downloads' },
          ],
        },
        {
          label: 'Concepts',
          translations: {
            'zh-TW': '核心概念',
          },
          items: [
            { slug: 'concepts/runtime-capability-discovery' },
            { slug: 'concepts/routing-envelopes' },
            { slug: 'concepts/personal-routing-profiles' },
            { slug: 'concepts/explicit-skill-lock' },
            { slug: 'concepts/phase-state-machine' },
            { slug: 'concepts/managed-goals' },
          ],
        },
        {
          label: 'Guides',
          translations: {
            'zh-TW': '指南',
          },
          items: [
            { slug: 'guides/install-plugin' },
            { slug: 'guides/install-skill' },
            { slug: 'guides/adoption' },
            { slug: 'guides/verified-host-integration' },
            { slug: 'guides/troubleshooting' },
          ],
        },
        {
          label: 'Evaluation',
          translations: {
            'zh-TW': '評測與證據',
          },
          items: [
            { slug: 'concepts/evaluation-evidence' },
            { slug: 'showcase' },
          ],
        },
        {
          label: 'Reference',
          translations: {
            'zh-TW': '參考資料',
          },
          items: [
            { slug: 'reference/mcp-tools' },
            { slug: 'reference/cli' },
            { slug: 'reference/local-state' },
            { slug: 'reference/security-boundaries' },
            { slug: 'reference/routing-contract' },
            { slug: 'reference/model-evaluation' },
          ],
        },
        {
          label: 'Contributing',
          translations: {
            'zh-TW': '參與貢獻',
          },
          items: [
            { slug: 'contributing/release-process' },
            { slug: 'contributing/roadmap' },
          ],
        },
        {
          label: 'Legacy V1',
          translations: {
            'zh-TW': 'V1 歷史版本',
          },
          items: [
            { slug: 'guides/migrate-v1-to-v2' },
            {
              label: 'V1.3.1 Release',
              link: 'https://github.com/eric861129/Workflow-skill-router/releases/tag/v1.3.1',
            },
          ],
        },
      ],
    }),
    excludeLegacySiteAssets,
  ],
});
