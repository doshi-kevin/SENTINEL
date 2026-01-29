import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const graphPath = path.join(
    process.cwd(),
    '..',
    'data',
    'model_ready',
    'graphs',
    `window_${id.padStart(4, '0')}.json`
  );

  try {
    const content = fs.readFileSync(graphPath, 'utf-8');
    return NextResponse.json(JSON.parse(content));
  } catch (error) {
    return NextResponse.json({ error: 'Graph not found' }, { status: 404 });
  }
}
