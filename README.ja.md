# WindowResizer

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

WindowResizer は、アプリケーションウィンドウを検索し、移動またはサイズ変更し、
保存したウィンドウプロファイルを繰り返し適用できる Windows デスクトップ
アプリケーションです。

現在文書化されているリリース: 0.01.4

## アプリ画面

![WindowResizer メインウィンドウ](docs/images/windowresizer-main-window.png)

## 主な機能

- 実行中のウィンドウを選択し、移動またはサイズ変更します。
- ウィンドウの位置とサイズを再利用可能なプロファイルとして保存します。
- 実行ファイルの完全パスでプロファイルを照合し、同じファイル名の
  アプリケーションも区別します。
- 実際のウィンドウに適用する前に、保存したレイアウトをプレビューします。
- 条件に一致する新しいウィンドウが検出されたとき、必要に応じてプロファイルを
  自動適用します。
- プロファイルごとの位置固定とマウスカーソルの制限を個別に有効化できます。
- プロファイル操作を素早く実行するためのグローバルショートカットを登録します。
- ライト、ダーク、高コントラストのテーマを選択でき、保存済みのウィンドウ座標に
  影響しないアプリケーション UI の表示倍率も調整できます。
- メインウィンドウを閉じた後もシステムトレイでアプリを利用でき、作業完了時には
  明示的な終了操作で完全に終了できます。
- 同一 Windows セッションでのアプリケーション重複起動を防ぎます。

## 必要環境

- Windows 10 または Windows 11
- 開発用の Python 3.12、またはビルド済みの Windows 実行ファイル

管理者権限で実行されている対象ウィンドウは、標準権限の WindowResizer プロセス
から操作できない場合があります。必要に応じて WindowResizer も同じ権限レベルで
実行してください。

## ソースから実行する

リポジトリのルートで依存関係をインストールし、アプリケーションを起動します。

~~~powershell
C:\Python312\python.exe -m pip install -r requirements.txt
C:\Python312\python.exe run_gui.py
~~~

文書内のコマンドでは、別のバージョンを指す既定の python が選ばれないよう、
検証済みの Python 3.12 パスを使用しています。

## 実行ファイルをビルドする

~~~powershell
C:\Python312\python.exe final_build.py
~~~

成功すると dist/WindowResizer.exe が生成されます。dist/ と build/ は生成物
であり、ソース管理には含まれません。

## 変更を検証する

変更した領域の重点回帰テストを実行してください。追跡対象のテストスイート全体を
実行するには、次を使用します。

~~~powershell
C:\Python312\python.exe -m unittest discover -s tests -p 'test_*.py'
~~~

## ドキュメント

インストールガイドとユーザーガイドは現在韓国語です。パッチノートは英語、韓国語、
簡体字中国語、日本語で提供しています。

- [インストールと実行ガイド（韓国語）](docs/INSTALLATION.md)
- [ユーザーガイド（韓国語）](docs/USER_GUIDE.md)
- [変更履歴: English](docs/CHANGELOG.md) | [한국어](docs/CHANGELOG.ko.md) |
  [中文](docs/CHANGELOG.zh-CN.md) | [日本語](docs/CHANGELOG.ja.md)

## リポジトリ構成

- src/: アプリケーションのソースコード
- run_gui.py: 開発起動エントリポイント
- final_build.py: PyInstaller ビルドスクリプト
- requirements.txt: Python の依存関係
- tests/: 追跡対象の回帰テスト
- docs/: ユーザー向け文書と画像
