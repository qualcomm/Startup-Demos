import fs from 'node:fs';
import path from 'node:path';

export function publishPicture(projectDirectory, picture, repoPath, publicDirectory) {
  if (typeof picture !== 'string' || !picture.trim()) return null;
  const root = fs.realpathSync(projectDirectory);
  const source = fs.realpathSync(path.resolve(root, picture));
  if (!source.startsWith(`${root}${path.sep}`) || !fs.statSync(source).isFile()) {
    throw new Error('Project picture must be a file inside its project directory');
  }
  const extension = path.extname(source).toLowerCase();
  if (!['.png', '.jpg', '.jpeg', '.gif', '.webp', '.avif', '.svg'].includes(extension)) {
    throw new Error(`Unsupported picture format: ${extension}`);
  }
  const identity = Buffer.from(repoPath).toString('base64url');
  const filename = `${identity}${extension}`;
  const destination = path.join(publicDirectory, 'project-pictures');
  fs.mkdirSync(destination, { recursive: true });
  fs.copyFileSync(source, path.join(destination, filename));
  return `project-pictures/${filename}`;
}