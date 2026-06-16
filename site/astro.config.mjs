import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

const siteUrl = 'https://huangchiyu.com';
const basePath = '/Workflow-skill-router';
const repoUrl = 'https://github.com/eric861129/Workflow-skill-router';
const ogImage = `${siteUrl}${basePath}/og/workflow-skill-router.png`;

export default defineConfig({
  site: siteUrl,
  base: basePath,
  integrations: [
    starlight({
      title: 'Workflow Skill Router',
      description:
        'A practical AI agent skill routing pattern for Codex Skills, workflow routers, and multi-skill agents.',
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
              'AI agent skill routing pattern, workflow router, Codex skills, multi-skill agents, agentic workflow, prompt engineering, developer tools',
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
          label: 'Start Here',
          translations: {
            'zh-TW': '開始使用',
          },
          items: [
            { slug: '' },
            { slug: 'guides/quickstart' },
            { slug: 'guides/blank-router-walkthrough' },
            { slug: 'guides/troubleshooting' },
            { slug: 'guides/adapters' },
            { slug: 'guides/downloads' },
            { slug: 'guides/adoption' },
          ],
        },
        {
          label: 'Examples',
          translations: {
            'zh-TW': '範例',
          },
          items: [
            { slug: 'showcase' },
            { slug: 'examples/routing-gallery' },
            { slug: 'examples/template-skill-catalog' },
            { slug: 'examples/case-studies' },
          ],
        },
        {
          label: 'Reference',
          translations: {
            'zh-TW': '參考',
          },
          items: [
            { slug: 'reference/routing-contract' },
            { slug: 'reference/routing-metrics-trends' },
            { slug: 'reference/analytics' },
            { slug: 'reference/validator' },
            { slug: 'reference/sample-skills' },
            { slug: 'reference/source-map' },
          ],
        },
      ],
    }),
  ],
});
